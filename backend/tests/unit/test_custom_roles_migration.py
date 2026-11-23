"""SQLite verification for the additive custom-role migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.pool import StaticPool

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic" / "versions" / "2026_11_23_1300-d4e6a8b2c1f3_custom_roles.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("custom_roles_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_custom_roles_migration_is_batch_safe_and_idempotent() -> None:
    engine = sa.create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata = sa.MetaData()
    sa.Table("tenants", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table("users", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    metadata.create_all(engine)
    migration = _load_migration()
    assert migration.revision == "d4e6a8b2c1f3"
    assert len(migration.revision) == 12
    assert migration.down_revision == "c3a7f1d9e2b5"

    with engine.connect() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.upgrade()
        inspector = sa.inspect(connection)
        assert "custom_roles" in inspector.get_table_names()
        assert "custom_role_id" in {
            column["name"] for column in inspector.get_columns("users")
        }
        unique_columns = [
            constraint["column_names"]
            for constraint in inspector.get_unique_constraints("custom_roles")
        ]
        assert ["tenant_id", "name"] in unique_columns
        assert {
            "ix_custom_roles_tenant_id",
            "ix_custom_roles_created_by",
            "ix_custom_roles_tenant_id_id",
        } <= {index["name"] for index in inspector.get_indexes("custom_roles")}

        migration.downgrade()
        migration.downgrade()
        inspector = sa.inspect(connection)
        assert "custom_roles" not in inspector.get_table_names()
        assert "custom_role_id" not in {
            column["name"] for column in inspector.get_columns("users")
        }
    engine.dispose()
