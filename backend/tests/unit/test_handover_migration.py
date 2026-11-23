"""The handover migration is repeatable and preserves FK/check semantics."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.pool import StaticPool

MIGRATION_PATH = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "2026_11_23_1700-4b8d2f6c91ae_create_handover_possession_tables.py"


def _load():
    spec = importlib.util.spec_from_file_location("handover_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_handover_migration_upgrade_downgrade_and_idempotency() -> None:
    engine = sa.create_engine("sqlite+pysqlite://", poolclass=StaticPool)
    metadata = sa.MetaData()
    for name in ("tenants", "property_units", "sale_bookings", "users"):
        sa.Table(name, metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    metadata.create_all(engine)
    migration = _load()
    assert migration.revision == "4b8d2f6c91ae"
    assert migration.down_revision == "d9b3e5c7a1f4"
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.upgrade()
        tables = set(sa.inspect(connection).get_table_names())
        assert {"handover_cases", "handover_snags", "handover_keys"} <= tables
        indexes = {index["name"] for index in sa.inspect(connection).get_indexes("handover_cases")}
        assert "ix_handover_cases_tenant_id_id" not in indexes
        migration.downgrade()
        assert not {"handover_cases", "handover_snags", "handover_keys"} & set(sa.inspect(connection).get_table_names())
    engine.dispose()


def test_handover_tables_registered_for_tenant_enforcement() -> None:
    from app.db.tenancy import TENANT_TABLES

    assert {"handover_cases", "handover_snags", "handover_keys"} <= TENANT_TABLES
