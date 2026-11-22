"""add durable per-tenant integration connections

Revision ID: a3b4c5d6e7f8
Revises: b7c8d9e0f1a2
Create Date: 2026-11-22 12:00:00

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create encrypted provider routing with globally unique page ids."""
    # Composite tenant_id_id indexes are auto-emitted by app.db.tenancy's
    # after_parent_attach listener, not created here.
    op.create_table(
        "integration_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("external_account_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("credentials_ciphertext", sa.Text(), nullable=False),
        sa.Column("webhook_verify_token_hash", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name=op.f("fk_integration_connections_project_id_projects"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_integration_connections_tenant_id_tenants"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_connections")),
        sa.UniqueConstraint("external_account_id", name="uq_integration_connections_external_account"),
    )
    op.create_index(op.f("ix_integration_connections_provider"), "integration_connections", ["provider"], unique=False)
    op.create_index(op.f("ix_integration_connections_project_id"), "integration_connections", ["project_id"], unique=False)
    op.create_index(op.f("ix_integration_connections_tenant_id"), "integration_connections", ["tenant_id"], unique=False)


def downgrade() -> None:
    """Drop the connection table, including the auto-emitted composite index."""
    op.drop_index("ix_integration_connections_tenant_id_id", table_name="integration_connections")
    op.drop_index(op.f("ix_integration_connections_tenant_id"), table_name="integration_connections")
    op.drop_index(op.f("ix_integration_connections_project_id"), table_name="integration_connections")
    op.drop_index(op.f("ix_integration_connections_provider"), table_name="integration_connections")
    op.drop_table("integration_connections")
