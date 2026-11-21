"""add tenant ownership and default-tenant backfill

Revision ID: c6e7d8a9b0f1
Revises: f7e8d9c0b1a2
Create Date: 2026-11-19 12:00:00
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa

revision: str = "c6e7d8a9b0f1"
down_revision: Union[str, None] = "f7e8d9c0b1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


def _existing_indexes(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table)}


def _ensure_index(name: str, table: str, columns: list[str], *, unique: bool = False) -> None:
    """Create an index only when it is not already present.

    The tenant model mixin also auto-attaches a composite index with the same
    naming convention; the guard keeps migration execution deterministic in
    either order and safe against partial previous runs.
    """

    if name in _existing_indexes(table):
        return
    op.create_index(name, table, columns, unique=unique)
TABLES = (
    "users", "projects", "project_facts", "fact_versions", "leads", "lead_assignments",
    "conversations", "messages", "visit_slots", "bookings", "handoffs", "follow_ups",
    "notifications", "notification_templates", "system_settings", "marketing_spends",
    "audit_logs", "refresh_tokens", "revoked_access_tokens",
)


def upgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "tenants" not in existing_tables:
        op.create_table(
            "tenants",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("slug", sa.String(length=100), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("brand_name", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("plan_id", sa.Uuid(), nullable=True),
            sa.Column("logo_path", sa.String(length=500), nullable=True),
            sa.Column("theme_json", sa.JSON(), nullable=False),
            sa.Column("country", sa.String(length=2), nullable=False),
            sa.Column("timezone", sa.String(length=64), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _ensure_index(op.f("ix_tenants_slug"), "tenants", ["slug"], unique=True)
    _ensure_index(op.f("ix_tenants_status"), "tenants", ["status"])
    op.execute(
        sa.text(
            "INSERT INTO tenants (id, slug, name, brand_name, status, plan_id, logo_path, theme_json, country, timezone, currency, created_at, updated_at) "
            "VALUES (:id, 'default', 'Default Tenant', 'Default Tenant', 'active', NULL, NULL, '{}', 'IN', 'UTC', 'INR', :now, :now)"
        ).bindparams(id=DEFAULT_TENANT_ID, now=datetime.now(UTC))
    )

    for table in TABLES:
        inspector = sa.inspect(op.get_bind())
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "tenant_id" not in columns:
            with op.batch_alter_table(table) as batch:
                batch.add_column(sa.Column("tenant_id", sa.Uuid(), nullable=True))
            op.execute(
                sa.table(table, sa.column("tenant_id", sa.Uuid())).update().values(
                    tenant_id=DEFAULT_TENANT_ID
                )
            )
            with op.batch_alter_table(table) as batch:
                batch.alter_column("tenant_id", existing_type=sa.Uuid(), nullable=False)
                batch.create_foreign_key(
                    f"fk_{table}_tenant_id_tenants", "tenants", ["tenant_id"], ["id"],
                    ondelete="RESTRICT",
                )
        _ensure_index(op.f(f"ix_{table}_tenant_id"), table, ["tenant_id"])
        composite_column = "jti" if table == "revoked_access_tokens" else "id"
        if table != "system_settings":
            _ensure_index(
                f"ix_{table}_tenant_id_{composite_column}",
                table,
                ["tenant_id", composite_column],
            )

    users_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    if "security_version" not in users_columns:
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("security_version", sa.Integer(), nullable=False, server_default="1"))
    refresh_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("refresh_tokens")}
    if "token_lookup" not in refresh_columns:
        with op.batch_alter_table("refresh_tokens") as batch:
            batch.add_column(sa.Column("token_lookup", sa.String(length=64), nullable=True))
    _ensure_index(op.f("ix_refresh_tokens_token_lookup"), "refresh_tokens", ["token_lookup"])

    if "password_reset_tokens" not in set(sa.inspect(op.get_bind()).get_table_names()):
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("token_lookup", sa.String(length=64), nullable=False),
            sa.Column("token_hash", sa.String(length=255), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _ensure_index(op.f("ix_password_reset_tokens_token_lookup"), "password_reset_tokens", ["token_lookup"])
    _ensure_index(op.f("ix_password_reset_tokens_user_id"), "password_reset_tokens", ["user_id"])
    _ensure_index(op.f("ix_password_reset_tokens_tenant_id"), "password_reset_tokens", ["tenant_id"])
    _ensure_index("ix_password_reset_tokens_tenant_id_id", "password_reset_tokens", ["tenant_id", "id"])
    for column in ("executive_id", "lead_id", "project_id", "scheduled_at", "status"):
        _ensure_index(op.f(f"ix_follow_ups_{column}"), "follow_ups", [column])

    project_constraints = {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints("projects")
    }
    if "uq_projects_tenant_id_slug" not in project_constraints:
        # The original global UNIQUE(slug) index becomes tenant-local: drop and
        # recreate slug as a plain (non-unique) index, then add the composite
        # unique constraint. Batch mode handles SQLite/Postgres portability.
        with op.batch_alter_table("projects") as batch:
            batch.drop_index("ix_projects_slug")
            batch.create_index("ix_projects_slug", ["slug"], unique=False)
            batch.create_unique_constraint("uq_projects_tenant_id_slug", ["tenant_id", "slug"])
    settings_pk = {column for column in [pk for pk in sa.inspect(op.get_bind()).get_pk_constraint("system_settings")["constrained_columns"]]}
    if settings_pk != {"tenant_id", "key"}:
        with op.batch_alter_table("system_settings") as batch:
            batch.drop_constraint("pk_system_settings", type_="primary")
            batch.create_primary_key("pk_system_settings", ["tenant_id", "key"])


def downgrade() -> None:
    for column in ("executive_id", "lead_id", "project_id", "scheduled_at", "status"):
        op.drop_index(op.f(f"ix_follow_ups_{column}"), table_name="follow_ups")
    with op.batch_alter_table("system_settings") as batch:
        batch.drop_constraint("pk_system_settings", type_="primary")
        batch.create_primary_key("pk_system_settings", ["key"])
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("uq_projects_tenant_id_slug", type_="unique")
        batch.drop_index("ix_projects_slug")
        batch.create_index("ix_projects_slug", ["slug"], unique=True)
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_token_lookup"), table_name="password_reset_tokens")
    op.drop_index(op.f("ix_password_reset_tokens_tenant_id"), table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_tenant_id_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("security_version")
    with op.batch_alter_table("refresh_tokens") as batch:
        batch.drop_index(op.f("ix_refresh_tokens_token_lookup"))
        batch.drop_column("token_lookup")
    for table in reversed(TABLES):
        with op.batch_alter_table(table) as batch:
            if table == "revoked_access_tokens":
                batch.drop_index(f"ix_{table}_tenant_id_jti")
            elif table != "system_settings":
                batch.drop_index(f"ix_{table}_tenant_id_id")
            batch.drop_index(op.f(f"ix_{table}_tenant_id"))
            batch.drop_constraint(f"fk_{table}_tenant_id_tenants", type_="foreignkey")
            batch.drop_column("tenant_id")
    op.drop_index(op.f("ix_tenants_status"), table_name="tenants")
    op.drop_index(op.f("ix_tenants_slug"), table_name="tenants")
    op.drop_table("tenants")
