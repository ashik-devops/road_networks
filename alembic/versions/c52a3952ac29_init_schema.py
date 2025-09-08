"""init schema

Revision ID: c52a3952ac29
Revises:
Create Date: 2025-09-03 17:15:28.672108

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = "c52a3952ac29"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable required extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # customers
    op.create_table(
        "customers",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_customer_name"),
    )

    # api_keys
    op.create_table(
        "api_keys",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("customer_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            pg.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_api_key_token_hash"),
    )
    op.create_index("ix_api_keys_customer", "api_keys", ["customer_id"])

    # networks
    op.create_table(
        "networks",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("customer_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", "name", name="uq_network_per_customer_name"),
    )
    op.create_index("ix_networks_customer", "networks", ["customer_id"])

    # network_versions
    op.create_table(
        "network_versions",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("network_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "valid_from",
            pg.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("valid_to", pg.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["network_id"], ["networks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="ck_version_window"
        ),
    )
    # partial unique index
    op.create_index(
        "uq_network_current_version",
        "network_versions",
        ["network_id"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    op.create_index("ix_versions_network", "network_versions", ["network_id"])

    # edges
    op.create_table(
        "edges",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("network_version_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(
                geometry_type="LINESTRING",
                srid=4326,
                spatial_index=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "properties",
            pg.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            pg.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["network_version_id"], ["network_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Spatial + helper indexes
    op.create_index(
        "ix_edges_geom", "edges", ["geom"], unique=False, postgresql_using="gist"
    )
    op.create_index("ix_edges_version", "edges", ["network_version_id"])


def downgrade() -> None:
    op.drop_index("ix_edges_version", table_name="edges")
    op.drop_index("ix_edges_geom", table_name="edges")
    op.drop_table("edges")

    op.drop_index("ix_versions_network", table_name="network_versions")
    op.drop_index("uq_network_current_version", table_name="network_versions")
    op.drop_table("network_versions")

    op.drop_index("ix_networks_customer", table_name="networks")
    op.drop_table("networks")

    op.drop_index("ix_api_keys_customer", table_name="api_keys")
    op.drop_table("api_keys")

    op.drop_table("customers")
