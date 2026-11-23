"""SQLite verification of the deal-desk tables migration.

Runs upgrade/downgrade against an in-memory database; the configured database
is never touched. Repeated upgrades prove idempotency, and the default matrix
seed must land exactly once per tenant with created_at supplied explicitly
(DEFAULT now() breaks on SQLite), including for tenants that already exist.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.pool import StaticPool

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "2026_11_23_1600-a7f3c1d92b64_deal_desk_cost_sheets_discount_matrix.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("deal_desk_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _base_metadata() -> sa.MetaData:
    """Pre-migration stand-ins for the FK targets the migration references."""

    metadata = sa.MetaData()
    sa.Table("tenants", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table("projects", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table("property_units", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    return metadata


def _run_upgrade(connection, migration) -> None:
    migration.op = Operations(MigrationContext.configure(connection))
    migration.upgrade()


def test_deal_desk_migration_is_idempotent_and_seeds_defaults() -> None:
    engine = sa.create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    metadata = _base_metadata()
    metadata.create_all(engine)
    tenant_a, tenant_b = uuid4(), uuid4()
    with engine.begin() as connection:
        connection.execute(
            sa.text("INSERT INTO tenants (id) VALUES (:id)"), {"id": str(tenant_a)}
        )
        connection.execute(
            sa.text("INSERT INTO tenants (id) VALUES (:id)"), {"id": str(tenant_b)}
        )

    migration = _load_migration()
    assert migration.revision == "a7f3c1d92b64"
    assert migration.down_revision == "a3f5c7e9b2d4"

    with engine.begin() as connection:
        _run_upgrade(connection, migration)
        # A partially migrated database must not fail a repeated upgrade.
        _run_upgrade(connection, migration)

        inspector = sa.inspect(connection)
        tables = set(inspector.get_table_names())
        assert {
            "deal_desk_cost_sheets",
            "deal_desk_discount_matrix_bands",
            "deal_desk_quotes",
        } <= tables

        index_names = {
            index["name"] for index in inspector.get_indexes("deal_desk_cost_sheets")
        }
        assert "uq_deal_desk_cost_sheets_project_sheet" in index_names

        rows = connection.execute(
            sa.text(
                "SELECT tenant_id, band_number, max_discount_percent, reason_required, "
                "blocked, created_at FROM deal_desk_discount_matrix_bands "
                "ORDER BY tenant_id, band_number"
            )
        ).fetchall()
        # Exactly one default ladder per tenant, never doubled by re-running.
        # Raw text reads return the stored dashless-hex UUID strings.
        assert len(rows) == 6
        assert {row[0] for row in rows} == {tenant_a.hex, tenant_b.hex}
        ladder = rows[:3]
        assert [row[1] for row in ladder] == [1, 2, 3]
        assert float(ladder[0][2]) == 2.00 and float(ladder[1][2]) == 5.00
        assert ladder[2][2] is None
        assert bool(ladder[1][3]) is True and bool(ladder[2][4]) is True
        # created_at was supplied explicitly, not left to a server default.
        assert all(row[5] is not None for row in rows)

        migration.downgrade()
        migration.downgrade()  # downgrade must also tolerate a missing table
        assert not {
            "deal_desk_cost_sheets",
            "deal_desk_discount_matrix_bands",
            "deal_desk_quotes",
        } & set(sa.inspect(connection).get_table_names())
    engine.dispose()


def test_migration_creates_tables_from_empty_base_and_tolerates_rerun() -> None:
    engine = sa.create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    _base_metadata().create_all(engine)
    migration = _load_migration()
    with engine.begin() as connection:
        _run_upgrade(connection, migration)
        _run_upgrade(connection, migration)  # no tenants: seeds nothing, no error
        count = connection.execute(
            sa.text("SELECT COUNT(*) FROM deal_desk_discount_matrix_bands")
        ).scalar()
        assert count == 0
    engine.dispose()


def test_matrix_band_checks_enforce_policy_shape() -> None:
    engine = sa.create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    _base_metadata().create_all(engine)
    migration = _load_migration()
    now = datetime.now(UTC)
    band = sa.table(
        "deal_desk_discount_matrix_bands",
        sa.column("id", sa.Uuid()),
        sa.column("tenant_id", sa.Uuid()),
        sa.column("band_number", sa.Integer()),
        sa.column("max_discount_percent", sa.Numeric(5, 2)),
        sa.column("reason_required", sa.Boolean()),
        sa.column("blocked", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    with engine.begin() as connection:
        _run_upgrade(connection, migration)
        tenant_id = uuid4()
        connection.execute(
            sa.text("INSERT INTO tenants (id) VALUES (:id)"), {"id": str(tenant_id)}
        )

        base = {
            "id": uuid4(), "tenant_id": tenant_id, "band_number": 9,
            "max_discount_percent": 7.0, "reason_required": True, "blocked": False,
            "created_at": now, "updated_at": now,
        }

        def values(**overrides) -> dict:
            row = dict(base)
            row["id"] = uuid4()
            row.update(overrides)
            return row

        connection.execute(band.insert().values(**values()))  # sane row inserts fine

        # A blocked band may not carry a covered threshold (ceiling only).
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(band.insert().values(**values(blocked=True)))
        # Percent out of range.
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(band.insert().values(**values(max_discount_percent=0)))
        with pytest.raises(sa.exc.IntegrityError):
            connection.execute(band.insert().values(**values(band_number=0)))
    engine.dispose()
