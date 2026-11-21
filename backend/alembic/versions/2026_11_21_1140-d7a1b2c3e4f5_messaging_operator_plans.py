"""Phase 3: messaging engine, operator identity, plan catalog, deployments.

Revision ID: d7a1b2c3e4f5
Revises: c6e7d8a9b0f1
Create Date: 2026-11-21 11:40:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d7a1b2c3e4f5"
down_revision: Union[str, None] = "c6e7d8a9b0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ensure_index(name: str, table: str, columns: list[str], *, unique: bool = False) -> None:
    """Guard index creation against the tenant-index auto-attach listener."""

    existing = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}
    if name in existing:
        return
    _create_index(name, table, columns, unique=unique)


def _has_table(name: str) -> bool:
    return name in set(sa.inspect(op.get_bind()).get_table_names())


def _create_table(name: str, *columns, **kwargs) -> None:
    if _has_table(name):
        return
    op.create_table(name, *columns, **kwargs)


def _create_index(name: str, table: str, columns: list[str], unique: bool = False, **kwargs) -> None:
    existing = {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes(table)}
    if name in existing:
        return
    op.create_index(name, table, columns, unique=unique, **kwargs)


def upgrade() -> None:
    # Outbound message templates (distinct from in-app notification_templates).
    _create_table(
        "message_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("language", sa.String(length=8), server_default="en", nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("provider_template_name", sa.String(length=160), nullable=True),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", "channel", "language", name="uq_message_templates_tenant_name_channel_language"),
    )
    _create_index("ix_message_templates_tenant_channel_language", "message_templates", ["tenant_id", "channel", "language"])
    _ensure_index("ix_message_templates_tenant_id_id", "message_templates", ["tenant_id", "id"])

    _create_table(
        "trigger_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("delay_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["message_templates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index("ix_trigger_rules_tenant_event_enabled", "trigger_rules", ["tenant_id", "event", "enabled"])
    _ensure_index("ix_trigger_rules_tenant_id_id", "trigger_rules", ["tenant_id", "id"])

    _create_table(
        "message_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=True),
        sa.Column("trigger_rule_id", sa.Uuid(), nullable=True),
        sa.Column("to_address", sa.String(length=320), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=32), server_default="log", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="QUEUED", nullable=False),
        sa.Column("provider_msg_id", sa.String(length=160), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["message_templates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["trigger_rule_id"], ["trigger_rules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_message_deliveries_tenant_idempotency"),
    )
    _create_index("ix_message_deliveries_status_next_attempt", "message_deliveries", ["status", "next_attempt_at"])
    _create_index("ix_message_deliveries_tenant_created_at", "message_deliveries", ["tenant_id", "created_at"])
    _ensure_index("ix_message_deliveries_tenant_id_id", "message_deliveries", ["tenant_id", "id"])

    # Single-column indexes matching ORM ``index=True`` declarations.
    _create_index("ix_message_templates_tenant_id", "message_templates", ["tenant_id"])
    _create_index("ix_trigger_rules_tenant_id", "trigger_rules", ["tenant_id"])
    _create_index("ix_trigger_rules_template_id", "trigger_rules", ["template_id"])
    _create_index("ix_message_deliveries_tenant_id", "message_deliveries", ["tenant_id"])
    _create_index("ix_message_deliveries_template_id", "message_deliveries", ["template_id"])
    _create_index("ix_message_deliveries_trigger_rule_id", "message_deliveries", ["trigger_rule_id"])
    _create_index("ix_message_deliveries_status", "message_deliveries", ["status"])
    _create_index("ix_message_deliveries_next_attempt_at", "message_deliveries", ["next_attempt_at"])
    _create_index("ix_message_deliveries_created_at", "message_deliveries", ["created_at"])

    # Cached language detection on leads (AI picks language once per lead).
    leads_columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("leads")}
    if "language" not in leads_columns:
        op.add_column("leads", sa.Column("language", sa.String(length=8), server_default="en", nullable=False))

    # Global platform operator identity (no tenant ownership by design).
    _create_table(
        "operator_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index(op.f("ix_operator_users_email"), "operator_users", ["email"], unique=True)

    _create_table(
        "operator_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("operator_id", sa.Uuid(), nullable=True),
        sa.Column("actor_email", sa.String(length=320), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["operator_id"], ["operator_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index(op.f("ix_operator_audit_logs_operator_id"), "operator_audit_logs", ["operator_id"])
    _create_index(op.f("ix_operator_audit_logs_action"), "operator_audit_logs", ["action"])
    _create_index(op.f("ix_operator_audit_logs_created_at"), "operator_audit_logs", ["created_at"])

    # Global subscription plan catalog.
    _create_table(
        "plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_paise", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("max_users", sa.Integer(), nullable=False),
        sa.Column("leads_per_month", sa.Integer(), nullable=False),
        sa.Column("whatsapp_msgs_per_month", sa.Integer(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index(op.f("ix_plans_code"), "plans", ["code"], unique=True)

    _create_table(
        "tenant_deployments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("environment", sa.String(length=64), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("deployment_url", sa.String(length=500), nullable=True),
        sa.Column("repository_url", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["requested_by"], ["operator_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    _create_index(op.f("ix_tenant_deployments_tenant_id"), "tenant_deployments", ["tenant_id"])
    _ensure_index("ix_tenant_deployments_tenant_id_id", "tenant_deployments", ["tenant_id", "id"])


def downgrade() -> None:
    op.drop_table("tenant_deployments")
    op.drop_table("plans")
    op.drop_table("operator_audit_logs")
    op.drop_table("operator_users")
    op.drop_column("leads", "language")
    op.drop_table("message_deliveries")
    op.drop_table("trigger_rules")
    op.drop_table("message_templates")
