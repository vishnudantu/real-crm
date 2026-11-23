"""SQLite verification for the service-desk KB + CSAT migration.

Runs upgrade/downgrade against an in-memory database built from real parent
tables (tenants/users/tickets); repeated upgrades prove idempotence and the
unique/check constraints prove the DDL is actually enforced. Also pins the
chain: down_revision must be the previous single head.
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
    / "2026_11_23_1400-a3f5c7e9b2d4_service_desk_kb_csat.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("kb_csat_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_kb_csat_migration_is_idempotent_and_enforces_constraints() -> None:
    engine = sa.create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    metadata = sa.MetaData()
    sa.Table("tenants", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table("users", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table("tickets", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    metadata.create_all(engine)

    migration = _load_migration()
    assert migration.revision == "a3f5c7e9b2d4"
    assert len(migration.revision) == 12
    assert migration.down_revision == "d9b3e5c7a1f4"

    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        inspector = sa.inspect(connection)
        assert {"kb_articles", "ticket_satisfaction"} <= set(inspector.get_table_names())
        # Partially migrated database must survive a repeated upgrade.
        migration.upgrade()

        index_names = {i["name"] for i in inspector.get_indexes("kb_articles")}
        assert "ix_kb_articles_tenant_status" in index_names
        assert "ix_kb_articles_tenant_id_id" in index_names
        unique_columns = [
            c["column_names"] for c in sa.inspect(connection).get_unique_constraints("kb_articles")
        ]
        assert ["tenant_id", "slug"] in unique_columns

        connection.execute(
            sa.text(
                "INSERT INTO kb_articles (id, title, slug, body_markdown, category,"
                " status, created_at, updated_at, tenant_id)"
                " VALUES (:id, :t, :s, :b, :c, :st, '2026-11-23 00:00:00',"
                " '2026-11-23 00:00:00', :tenant)"
            ),
            {
                "id": "00000000-0000-4000-8000-000000000001",
                "t": "Loan FAQ", "s": "loan-faq", "b": "Body", "c": "Loans",
                "st": "PUBLISHED", "tenant": "00000000-0000-4000-8000-0000000000a1",
            },
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO kb_articles (id, title, slug, body_markdown, category,"
                    " status, created_at, updated_at, tenant_id)"
                    " VALUES (:id, 'Dup', 'loan-faq', 'B', 'Loans', 'DRAFT',"
                    " '2026-11-23 00:00:00', '2026-11-23 00:00:00', :tenant)"
                ),
                {
                    "id": "00000000-0000-4000-8000-000000000002",
                    "tenant": "00000000-0000-4000-8000-0000000000a1",
                },
            )
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO kb_articles (id, title, slug, body_markdown, category,"
                    " status, created_at, updated_at, tenant_id)"
                    " VALUES (:id, 'Bad', 'bad', 'B', 'C', 'ARCHIVED',"
                    " '2026-11-23 00:00:00', '2026-11-23 00:00:00', :tenant)"
                ),
                {
                    "id": "00000000-0000-4000-8000-000000000003",
                    "tenant": "00000000-0000-4000-8000-0000000000a1",
                },
            )

        satisfaction_columns = {
            c["name"] for c in sa.inspect(connection).get_columns("ticket_satisfaction")
        }
        assert {"rating", "feedback", "responded_at", "created_at", "tenant_id"} <= (
            satisfaction_columns
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO ticket_satisfaction (id, ticket_id, rating, created_at,"
                    " tenant_id) VALUES (:id, :t, 7, '2026-11-23 00:00:00', :tenant)"
                ),
                {
                    "id": "00000000-0000-4000-8000-000000000004",
                    "t": "00000000-0000-4000-8000-0000000000b1",
                    "tenant": "00000000-0000-4000-8000-0000000000a1",
                },
            )

        assert "closed_at" in {
            c["name"] for c in sa.inspect(connection).get_columns("tickets")
        }

        migration.downgrade()
        inspector = sa.inspect(connection)
        assert not ({"kb_articles", "ticket_satisfaction"} & set(inspector.get_table_names()))
        assert "closed_at" not in {
            c["name"] for c in inspector.get_columns("tickets")
        }
        # A second downgrade against the already-rolled-back database is safe.
        migration.downgrade()
    engine.dispose()
