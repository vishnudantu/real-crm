"""tenant-ai: per-tenant AI provider configuration with encrypted keys

Revision ID: b3c4d5e6f7a8
Revises: f1a2b3c4d5e6
Create Date: 2026-11-22 22:10:00

Stores each tenant's own chat-provider selection. The API key lives only in
``api_key_ciphertext`` (Fernet, via the omnichannel credential vault); a
unique partial index keeps at most one active provider per tenant.

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3c4d5e6f7a8"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the tenant AI provider table.

    Composite tenant_id_id indexes are auto-emitted by app.db.tenancy's
    after_parent_attach listener; they are intentionally absent here.
    """
    op.create_table(
        "tenant_ai_providers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("api_key_ciphertext", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_tenant_ai_providers_created_by_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_tenant_ai_providers_tenant_id_tenants"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_ai_providers")),
    )
    op.create_index(op.f("ix_tenant_ai_providers_tenant_id"), "tenant_ai_providers", ["tenant_id"], unique=False)
    # One active provider per tenant (partial unique index; PG + SQLite 3.8+).
    op.create_index(
        "uq_tenant_ai_providers_active_tenant",
        "tenant_ai_providers",
        ["tenant_id"],
        unique=True,
        sqlite_where=sa.text("is_active"),
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index("uq_tenant_ai_providers_active_tenant", table_name="tenant_ai_providers")
    op.drop_index("ix_tenant_ai_providers_tenant_id_id", table_name="tenant_ai_providers")
    op.drop_index(op.f("ix_tenant_ai_providers_tenant_id"), table_name="tenant_ai_providers")
    op.drop_table("tenant_ai_providers")
