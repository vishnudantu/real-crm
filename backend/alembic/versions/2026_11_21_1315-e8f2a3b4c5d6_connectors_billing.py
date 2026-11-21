"""Phase 4+5: connector ingestion events, subscriptions, invoices, webhooks.

Revision ID: e8f2a3b4c5d6
Revises: d7a1b2c3e4f5
Create Date: 2026-11-21 13:15:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e8f2a3b4c5d6"
down_revision: Union[str, None] = "d7a1b2c3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_index(name: str, table: str, columns: list[str], unique: bool = False, **kwargs) -> None:
    existing = {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table)}
    if name in existing:
        return
    op.create_index(name, table, columns, unique=unique, **kwargs)


def upgrade() -> None:
    op.create_table(
        "lead_ingestion_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index("ix_lead_ingestion_provider_external", "lead_ingestion_events", ["provider", "external_id"], unique=True)
    _create_index("ix_lead_ingestion_tenant_created_at", "lead_ingestion_events", ["tenant_id", "received_at"])
    _create_index("ix_lead_ingestion_events_tenant_id", "lead_ingestion_events", ["tenant_id"])
    _create_index("ix_lead_ingestion_events_lead_id", "lead_ingestion_events", ["lead_id"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("razorpay_plan_id", sa.String(length=128), nullable=True),
        sa.Column("razorpay_subscription_id", sa.String(length=128), nullable=True, unique=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index(op.f("ix_subscriptions_plan_id"), "subscriptions", ["plan_id"])
    _create_index(op.f("ix_subscriptions_status"), "subscriptions", ["status"])
    _create_index("ix_subscriptions_tenant_id_id", "subscriptions", ["tenant_id", "id"])
    _create_index("ix_subscriptions_tenant_id", "subscriptions", ["tenant_id"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=True),
        sa.Column("razorpay_invoice_id", sa.String(length=128), nullable=True),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "razorpay_invoice_id", name="uq_invoices_tenant_razorpay"),
    )
    _create_index(op.f("ix_invoices_subscription_id"), "invoices", ["subscription_id"])
    _create_index(op.f("ix_invoices_razorpay_invoice_id"), "invoices", ["razorpay_invoice_id"])
    _create_index("ix_invoices_tenant_id_id", "invoices", ["tenant_id", "id"])
    _create_index("ix_invoices_tenant_id", "invoices", ["tenant_id"])

    # Global provider event ledger for replay protection (no tenant_id).
    op.create_table(
        "billing_webhook_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=160), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index(op.f("ix_billing_webhook_events_event_id"), "billing_webhook_events", ["event_id"], unique=True)


def downgrade() -> None:
    op.drop_table("billing_webhook_events")
    op.drop_table("invoices")
    op.drop_table("subscriptions")
    op.drop_table("lead_ingestion_events")
