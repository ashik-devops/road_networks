from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import sqlalchemy as sa
from psycopg2.extras import execute_values
from app.db import raw_cursor_from_session


class GeoJSONParseError(ValueError):
    """Raised when incoming GeoJSON is invalid or unsupported for this API."""

    pass


def ts_or_now(at: Optional[datetime]) -> datetime:

    # Return a timezone-aware UTC timestamp

    if at is None:
        return datetime.now(timezone.utc)
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def version_at(db, network_id: str, ts: datetime) -> Optional[str]:

    # Return the version_id valid at ts for this network or None if no version matches

    return db.execute(
        sa.text(
            """
            SELECT id
            FROM network_versions
            WHERE network_id = :nid
              AND valid_from <= :ts
              AND (valid_to IS NULL OR :ts < valid_to)
            ORDER BY valid_from DESC
            LIMIT 1
        """
        ),
        {"nid": network_id, "ts": ts},
    ).scalar_one_or_none()


def open_new_version(db, network_id: str, ts: Optional[datetime] = None) -> str:

    # Close any current version and open a new one starting at ts

    if ts is None:
        ts = datetime.now(timezone.utc)

    db.execute(
        sa.text(
            """
        UPDATE network_versions
           SET valid_to = :ts
         WHERE network_id = :nid AND valid_to IS NULL
    """
        ),
        {"nid": network_id, "ts": ts},
    )
    # Returns the new version UUID
    return db.execute(
        sa.text(
            """
        INSERT INTO network_versions(network_id, valid_from, valid_to)
        VALUES (:nid, :ts, NULL)
        RETURNING id
    """
        ),
        {"nid": network_id, "ts": ts},
    ).scalar_one()


def ensure_network(db, customer_id: str, name: str) -> str:

    # Upsert (customer_id, name) into networks and return the network UUID.

    return db.execute(
        sa.text(
            """
        INSERT INTO networks(customer_id, name)
        VALUES (:cid, :name)
        ON CONFLICT (customer_id, name) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
    """
        ),
        {"cid": customer_id, "name": name},
    ).scalar_one()


def load_geojson_bytes(data: bytes) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:

    # Parse a GeoJSON FeatureCollection
    try:
        doc = json.loads(data.decode("utf-8"))
    except Exception as e:
        raise GeoJSONParseError("Invalid JSON") from e

    if doc.get("type") != "FeatureCollection":
        raise GeoJSONParseError("Expected GeoJSON FeatureCollection")

    out: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
    for feat in doc.get("features", []):
        if not feat or feat.get("type") != "Feature":
            continue
        geom = feat.get("geometry")
        if not geom:
            continue
        props = feat.get("properties") or {}
        gtype = geom.get("type")

        if gtype == "LineString":
            if not geom.get("coordinates"):
                raise GeoJSONParseError("LineString has empty coordinates")
            out.append((geom, props))

    if not out:
        raise GeoJSONParseError("No LineString/MultiLineString features found")

    return out


def insert_edges(db, version_id: str, features):
    vals = []
    for geom, props in features:
        vals.append(
            (
                str(version_id),
                json.dumps(geom, separators=(",", ":")),
                json.dumps(props, separators=(",", ":")),
            )
        )
    if not vals:
        return 0

    with raw_cursor_from_session(db) as cur:
        execute_values(
            cur,
            "INSERT INTO edges (network_version_id, geom, properties) VALUES %s",
            vals,
            template="(%s::uuid, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s::jsonb)",
        )
    return len(vals)
