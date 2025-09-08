# alembic/env.py
from __future__ import annotations
import os
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from app.models import Base  # import your Base so autogenerate sees models

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Point Alembic at model metadata
target_metadata = Base.metadata

# Skip Postgres system + PostGIS schemas in diffs
SYSTEM_SCHEMAS = {"pg_catalog", "information_schema", "tiger", "tiger_data", "topology"}


def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table" and name == "alembic_version":
        return False
    obj_schema = getattr(obj, "schema", None)
    if obj_schema in SYSTEM_SCHEMAS:
        return False
    return True


def run_migrations_offline():
    url = os.getenv(
        "DATABASE_URL",
        config.get_main_option(
            "sqlalchemy.url",
            "postgresql+psycopg://postgres:postgres@localhost:5432/postgres",
        ),
    )
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # Force Alembic to use env var if provided
    config.set_main_option(
        "sqlalchemy.url",
        os.getenv(
            "DATABASE_URL",
            config.get_main_option(
                "sqlalchemy.url",
                "postgresql+psycopg://postgres:postgres@db:5432/postgres",
            ),
        ),
    )
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
