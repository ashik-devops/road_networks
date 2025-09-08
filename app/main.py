from fastapi import FastAPI
from fastapi.responses import JSONResponse
import sqlalchemy as sa
from datetime import datetime
from typing import Optional
from fastapi import Query, Depends, File, Form, UploadFile, HTTPException
from uuid import UUID
from app.db import get_db
from app.auth import withApiAuth

from app.services import (
    ts_or_now,
    version_at,
    open_new_version,
    ensure_network,
    load_geojson_bytes,
    insert_edges,
    GeoJSONParseError,
)

app = FastAPI(title="Road Networks API")


@app.post("/networks")
async def create_network(
    name: str = Form(...),
    file: UploadFile = File(...),
    customer_id: str = Depends(withApiAuth),
    db=Depends(get_db),
):
    try:
        data = await file.read()
        try:
            features = load_geojson_bytes(data)
        except GeoJSONParseError as e:
            raise HTTPException(status_code=400, detail=str(e))

        network_id = ensure_network(db, customer_id, name)
        version_id = open_new_version(db, network_id)
        count = insert_edges(db, version_id, features)

        db.commit()  # <- commit the existing session txn
        return {
            "network_id": network_id,
            "version_id": version_id,
            "edges_inserted": count,
        }

    except Exception:
        db.rollback()
        raise


@app.post("/networks/update")
async def update_network(
    name: str = Form(...),
    file: UploadFile = File(...),
    customer_id: str = Depends(withApiAuth),
    db=Depends(get_db),
):
    try:
        # find the network owned by this customer
        net_id = db.execute(
            sa.text(
                """
            SELECT id FROM networks
            WHERE customer_id = :cid AND name = :name
        """
            ),
            {"cid": customer_id, "name": name},
        ).scalar_one_or_none()
        if not net_id:
            raise HTTPException(status_code=404, detail="Network not found")

        data = await file.read()
        try:
            features = load_geojson_bytes(data)
        except GeoJSONParseError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # open a new version & insert edges
        version_id = open_new_version(db, net_id)
        count = insert_edges(db, version_id, features)

        db.commit()
        return {"network_id": net_id, "version_id": version_id, "edges_inserted": count}

    except Exception:
        db.rollback()
        raise


@app.get(
    "/networks/{network_id}/edges",
    response_class=JSONResponse,
    summary="Get edges as GeoJSON at a point in time (Task 3)",
)
def get_edges_by_id(
    network_id: UUID,
    datetime_param: Optional[datetime] = Query(
        None,
        alias="datetime",
        description="RFC3339 timestamp (e.g., 2025-09-06T05:10:00Z). Default: now (UTC).",
    ),
    customer_id: str = Depends(withApiAuth),
    db=Depends(get_db),
):
    ts = ts_or_now(datetime_param)

    # authorize
    owns = db.execute(
        sa.text("SELECT 1 FROM networks WHERE id = :nid AND customer_id = :cid"),
        {"nid": str(network_id), "cid": customer_id},
    ).scalar_one_or_none()
    if not owns:
        raise HTTPException(status_code=404, detail="Network not found")

    # find version
    version_id = version_at(db, str(network_id), ts)
    if not version_id:
        return JSONResponse(
            content={"type": "FeatureCollection", "features": []},
            media_type="application/geo+json",
        )

    # build FeatureCollection in Postgres
    sql = sa.text(
        """
        WITH f AS (
            SELECT
                e.id,
                e.properties,
                ST_AsGeoJSON(
                    CASE
                        WHEN ST_SRID(e.geom) = 4326 THEN e.geom
                        ELSE ST_Transform(e.geom, 4326)
                    END
                )::jsonb AS geom_json
            FROM edges e
            WHERE e.network_version_id = :vid
            ORDER BY e.id
        )
        SELECT jsonb_build_object(
            'type','FeatureCollection',
            'features', COALESCE(
                jsonb_agg(
                    jsonb_build_object(
                        'type','Feature',
                        'id', f.id,
                        'geometry', f.geom_json,
                        'properties', f.properties
                    )
                    ORDER BY f.id
                ),
                '[]'::jsonb
            )
        ) AS fc
        FROM f;
    """
    )

    fc = db.execute(sql, {"vid": str(version_id)}).scalar_one()
    return JSONResponse(content=fc, media_type="application/geo+json")
