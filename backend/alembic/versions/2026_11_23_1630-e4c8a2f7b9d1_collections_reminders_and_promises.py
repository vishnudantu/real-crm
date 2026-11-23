"""collections: reminder dedupe ledger + installment payment promises

Revision ID: e4c8a2f7b9d1
Revises: d9b3e5c7a1f4
Create Date: 2026-11-23 16:30:00

Creates two tenant-owned tables for the collections command centre:

- collection_reminders: one row per (tenant, installment, offset_key), the
  dedupe guard for the daily reminder sequencer.
- installment_promises: buyer promises to pay; record-only, never alters
  installment/receipt balances.

Idempotent (guarded on existing tables), batch-safe (created with plain
create_table so SQLite needs no ALTER), and the composite
``ix_<table>_tenant_id_id`` indexes are auto-emitted by app.db.tenancy's
after_parent_attach listener, so they are intentionally absent here.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4c8a2f7b9d1"
down_revision: Union[str, None] = "d9b3e5c7a1f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "collection_reminders" not in tables:
        op.create_table(
            "collection_reminders",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("installment_id", sa.Uuid(), nullable=False),
            sa.Column("offset_key", sa.String(length=8), nullable=False),
            sa.Column("channel", sa.String(length=16), nullable=False),
            sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "queued_at", sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
            ),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
            ),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.ForeignKeyConstraint(
                ["installment_id"], ["installments.id"],
                name=op.f("fk_collection_reminders_installment_id_installments"),
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name=op.f("fk_collection_reminders_tenant_id_tenants"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_reminders")),
            sa.UniqueConstraint(
                "tenant_id", "installment_id", "offset_key",
                name="uq_collection_reminders_tenant_installment_offset",
            ),
        )
        op.create_index(
            op.f("ix_collection_reminders_installment_id"),
            "collection_reminders", ["installment_id"], unique=False,
        )
        op.create_index(
            op.f("ix_collection_reminders_tenant_id"),
            "collection_reminders", ["tenant_id"], unique=False,
        )
        op.create_index(
            "ix_collection_reminders_tenant_scheduled",
            "collection_reminders", ["tenant_id", "scheduled_for"], unique=False,
        )

    if "installment_promises" not in tables:
        op.create_table(
            "installment_promises",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("installment_id", sa.Uuid(), nullable=False),
            sa.Column("amount_paise", sa.BigInteger(), nullable=False),
            sa.Column("promised_on", sa.Date(), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_by_id", sa.Uuid(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
            ),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.CheckConstraint(
                "amount_paise >= 0",
                name="ck_installment_promises_amount_non_negative",
            ),
            sa.ForeignKeyConstraint(
                ["installment_id"], ["installments.id"],
                name=op.f("fk_installment_promises_installment_id_installments"),
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["created_by_id"], ["users.id"],
                name=op.f("fk_installment_promises_created_by_id_users"),
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name=op.f("fk_installment_promises_tenant_id_tenants"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_installment_promises")),
        )
        op.create_index(
            op.f("ix_installment_promises_installment_id"),
            "installment_promises", ["installment_id"], unique=False,
        )
        op.create_index(
            op.f("ix_installment_promises_tenant_id"),
            "installment_promises", ["tenant_id"], unique=False,
        )
        op.create_index(
            "ix_installment_promises_tenant_installment",
            "installment_promises", ["tenant_id", "installment_id"], unique=False,
        )
        op.create_index(
            "ix_installment_promises_tenant_promised_on",
            "installment_promises", ["tenant_id", "promised_on"], unique=False,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "installment_promises" in tables:
        op.drop_index("ix_installment_promises_tenant_promised_on", table_name="installment_promises")
        op.drop_index("ix_installment_promises_tenant_installment", table_name="installment_promises")
        op.drop_index(op.f("ix_installment_promises_tenant_id"), table_name="installment_promises")
        op.drop_index(op.f("ix_installment_promises_installment_id"), table_name="installment_promises")
        existing_indexes = {ix["name"] for ix in inspector.get_indexes("installment_promises")}
        if "ix_installment_promises_tenant_id_id" in existing_indexes:
            op.drop_index("ix_installment_promises_tenant_id_id", table_name="installment_promises")
        op.drop_table("installment_promises")

    if "collection_reminders" in tables:
        op.drop_index("ix_collection_reminders_tenant_scheduled", table_name="collection_reminders")
        op.drop_index(op.f("ix_collection_reminders_tenant_id"), table_name="collection_reminders")
        op.drop_index(op.f("ix_collection_reminders_installment_id"), table_name="collection_reminders")
        existing_indexes = {ix["name"] for ix in inspector.get_indexes("collection_reminders")}
        if "ix_collection_reminders_tenant_id_id" in existing_indexes:
            op.drop_index("ix_collection_reminders_tenant_id_id", table_name="collection_reminders")
        op.drop_table("collection_reminders")
