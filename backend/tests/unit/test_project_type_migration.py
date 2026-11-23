"""SQLite verification of the additive projects.project_type migration.

Runs upgrade/downgrade against an in-memory database; the configured database
is never touched. Repeated upgrades prove the migration is idempotent.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "2026_11_23_1200-e2b7c4a9d1f6_add_project_type.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("project_type_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_project_type_migration_is_idempotent_and_enforces_values() -> None:
    engine = sa.create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    metadata = sa.MetaData()
    sa.Table(
        "projects",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
    )
    metadata.create_all(engine)
    migration = _load_migration()
    assert migration.revision == "e2b7c4a9d1f6"
    assert migration.down_revision == "c3a7f1d9e2b5"

    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        columns = {column["name"] for column in sa.inspect(connection).get_columns("projects")}
        assert "project_type" in columns

        # A partially migrated database must not fail a repeated upgrade.
        migration.upgrade()

        connection.execute(
            sa.text("INSERT INTO projects (id, name, project_type) VALUES (:id, 'A', 'VILLA')"),
            {"id": "00000000-0000-0000-0000-000000000001"},
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text("INSERT INTO projects (id, name, project_type) VALUES (:id, 'B', 'IGLOO')"),
                {"id": "00000000-0000-0000-0000-000000000002"},
            )

        migration.downgrade()
        assert "project_type" not in {
            column["name"] for column in sa.inspect(connection).get_columns("projects")
        }
    engine.dispose()
