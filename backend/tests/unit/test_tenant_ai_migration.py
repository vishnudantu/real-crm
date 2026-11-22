"""SQLite-only verification for the tenant_ai_providers Alembic migration.

Executes the migration's upgrade/downgrade against a throwaway in-memory
SQLite database with just the FK parent tables present. The real DB is never
touched. ``op`` is swapped for a connection-bound Operations object so the
same DDL Alembic would emit runs directly on SQLite.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.pool import StaticPool

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "2026_11_22_2210-b3c4d5e6f7a8_tenant_ai_provider_configuration.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("tenant_ai_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_parent_tables(metadata: sa.MetaData) -> None:
    sa.Table("tenants", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table("users", metadata, sa.Column("id", sa.Uuid(), primary_key=True))


def test_migration_creates_and_drops_table_on_sqlite() -> None:
    engine = sa.create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    metadata = sa.MetaData()
    _create_parent_tables(metadata)
    metadata.create_all(engine)

    migration = _load_migration()
    assert migration.revision == "b3c4d5e6f7a8"
    assert migration.down_revision == "f1a2b3c4d5e6"

    with engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        migration.op = Operations(ctx)

        migration.upgrade()
        inspector = sa.inspect(connection)
        assert "tenant_ai_providers" in inspector.get_table_names()
        index_names = {i["name"] for i in inspector.get_indexes("tenant_ai_providers")}
        assert "uq_tenant_ai_providers_active_tenant" in index_names
        assert "ix_tenant_ai_providers_tenant_id" in index_names

        migration.downgrade()
        inspector = sa.inspect(connection)
        assert "tenant_ai_providers" not in inspector.get_table_names()
    engine.dispose()
