"""approval_requests: generic entity-agnostic approval state machine

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-11-22 22:00:00

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the tenant-owned approval request table.

    The composite tenant_id_id index is auto-emitted by app.db.tenancy's
    after_parent_attach listener, so it is intentionally absent here.
    """
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_type", sa.String(length=48), nullable=False),
        sa.Column("reference_type", sa.String(length=48), nullable=False),
        sa.Column("reference_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by_id", sa.Uuid(), nullable=True),
        sa.Column("approver_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="PENDING", nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','CANCELLED')",
            name=op.f("ck_approval_requests_approval_request_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_id"], ["users.id"],
            name=op.f("fk_approval_requests_requested_by_id_users"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["approver_id"], ["users.id"],
            name=op.f("fk_approval_requests_approver_id_users"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_approval_requests_tenant_id_tenants"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approval_requests")),
    )
    op.create_index(op.f("ix_approval_requests_reference_id"), "approval_requests", ["reference_id"], unique=False)
    op.create_index(op.f("ix_approval_requests_tenant_id"), "approval_requests", ["tenant_id"], unique=False)
    op.create_index("ix_approval_requests_tenant_status", "approval_requests", ["tenant_id", "status"], unique=False)
    op.create_index("ix_approval_requests_tenant_request_type", "approval_requests", ["tenant_id", "request_type"], unique=False)


def downgrade() -> None:
    """Drop the approval table, including the auto-emitted composite index."""
    op.drop_index("ix_approval_requests_tenant_id_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_tenant_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_tenant_request_type", table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_tenant_id"), table_name="approval_requests")
    op.drop_index(op.f("ix_approval_requests_reference_id"), table_name="approval_requests")
    op.drop_table("approval_requests")
