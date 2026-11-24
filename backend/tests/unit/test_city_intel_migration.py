"""SQLite round-trip verification for the City Intelligence Phase 1 migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.pool import StaticPool

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic" / "versions" / "2026_11_24_1000-c7a1f2d4e8b9_city_intelligence_phase1.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("city_intel_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_city_intel_migration_creates_and_drops_tables_on_sqlite() -> None:
    engine = sa.create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    metadata = sa.MetaData()
    sa.Table("tenants", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table("projects", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    metadata.create_all(engine)

    migration = _load_migration()
    assert migration.revision == "c7a1f2d4e8b9"
    assert len(migration.revision) == 12
    assert migration.down_revision == "4b8d2f6c91ae"

    with engine.connect() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.upgrade()  # idempotent: second run is a no-op

        inspector = sa.inspect(connection)
        assert "project_amenities" in inspector.get_table_names()
        assert "locality_reports" in inspector.get_table_names()

        # The tenancy listener auto-emits ix_<table>_tenant_id_id during ORM
        # create_all. The migration must not create a *second* copy of it.
        for table in ("project_amenities", "locality_reports"):
            index_names = [i["name"] for i in inspector.get_indexes(table)]
            assert index_names.count(f"ix_{table}_tenant_id_id") <= 1

        migration.downgrade()
        inspector = sa.inspect(connection)
        assert "project_amenities" not in inspector.get_table_names()
        assert "locality_reports" not in inspector.get_table_names()
    engine.dispose()
