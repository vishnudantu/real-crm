"""broker/channel-partner registry

Revision ID: e6f7a8b9c0d1
Revises: c5d6e7f8a9b0
Create Date: 2026-11-22 22:00:00

The requested d5e6f7a8b9c0 revision id was already allocated to team chat;
this revision uses the next unique id and the actual current head as parent.

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the broker table.

    The composite (tenant_id, id) index is auto-emitted by app.db.tenancy's
    after_parent_attach listener; it is intentionally absent here.
    """
    op.create_table(
        "brokers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agency_name", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("rera_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="ACTIVE", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"],
            name=op.f("fk_brokers_created_by_users"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_brokers_tenant_id_tenants"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brokers")),
        sa.UniqueConstraint(
            "tenant_id", "agency_name", "contact_name",
            name="uq_brokers_tenant_agency_contact",
        ),
    )
    op.create_index(op.f("ix_brokers_agency_name"), "brokers", ["agency_name"], unique=False)
    op.create_index(op.f("ix_brokers_tenant_id"), "brokers", ["tenant_id"], unique=False)


def downgrade() -> None:
    # Dropping the table removes its indexes. Only drop the composite index
    # when the application model listener created it; a migration-only SQLite
    # context intentionally has no listener and therefore no such index.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {
        index["name"] for index in inspector.get_indexes("brokers")
    }
    if "ix_brokers_tenant_id_id" in existing_indexes:
        op.drop_index("ix_brokers_tenant_id_id", table_name="brokers")
    op.drop_table("brokers")
