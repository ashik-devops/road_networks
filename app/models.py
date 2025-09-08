# app/models.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Any
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects import postgresql as pg
from geoalchemy2 import Geometry


SRID = 4326  # store lon/lat in WGS84


class Base(DeclarativeBase):
    pass


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[sa.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)

    api_keys: Mapped[List["APIKey"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    networks: Mapped[List["Network"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[sa.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        primary_key=True,
    )
    customer_id: Mapped[sa.UUID] = mapped_column(
        pg.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE")
    )
    token_hash: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        pg.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
    )

    customer: Mapped["Customer"] = relationship(back_populates="api_keys")


class Network(Base):
    __tablename__ = "networks"

    id: Mapped[sa.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        primary_key=True,
    )
    customer_id: Mapped[sa.UUID] = mapped_column(
        pg.UUID(as_uuid=True), sa.ForeignKey("customers.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)

    customer: Mapped["Customer"] = relationship(back_populates="networks")
    versions: Mapped[List["NetworkVersion"]] = relationship(
        back_populates="network", cascade="all, delete-orphan"
    )

    __table_args__ = (
        sa.UniqueConstraint("customer_id", "name", name="uq_network_per_customer_name"),
    )


class NetworkVersion(Base):
    __tablename__ = "network_versions"

    id: Mapped[sa.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        primary_key=True,
    )
    network_id: Mapped[sa.UUID] = mapped_column(
        pg.UUID(as_uuid=True), sa.ForeignKey("networks.id", ondelete="CASCADE")
    )
    # Validity window for time-travel queries:
    valid_from: Mapped[datetime] = mapped_column(
        pg.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
    )
    valid_to: Mapped[Optional[datetime]] = mapped_column(
        pg.TIMESTAMP(timezone=True), nullable=True
    )

    network: Mapped["Network"] = relationship(back_populates="versions")
    edges: Mapped[List["Edge"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Only one current version per network:
        sa.Index(
            "uq_network_current_version",
            "network_id",
            unique=True,
            postgresql_where=sa.text("valid_to IS NULL"),
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="ck_version_window"
        ),
    )


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[sa.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        primary_key=True,
    )
    network_version_id: Mapped[sa.UUID] = mapped_column(
        pg.UUID(as_uuid=True),
        sa.ForeignKey("network_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Store the centerline geometry; GeoJSON is LINESTRING in SRID 4326.
    geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=SRID, spatial_index=False),
        nullable=False,
    )
    # Raw properties from GeoJSON:
    properties: Mapped[dict] = mapped_column(
        pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        pg.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
    )

    version: Mapped["NetworkVersion"] = relationship(back_populates="edges")

    __table_args__ = (
        # Spatial index (explicit in migration):
        sa.Index("ix_edges_geom", "geom", postgresql_using="gist"),
        sa.Index("ix_edges_version", "network_version_id"),
    )
