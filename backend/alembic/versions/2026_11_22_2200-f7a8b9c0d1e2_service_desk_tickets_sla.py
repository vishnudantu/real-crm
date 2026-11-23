"""service desk: support tickets with SLA deadlines and comment threads

Revision ID: f7a8b9c0d1e2
Revises: f8a9b0c1d2e3
Create Date: 2026-11-22 22:00:00

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create ticket + ticket_comments tables.

    Composite tenant_id_id indexes are auto-emitted by app.db.tenancy's
    after_parent_attach listener; they are intentionally absent here.
    """
    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_number", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=16), server_default="GENERAL", nullable=False),
        sa.Column("priority", sa.String(length=16), server_default="MEDIUM", nullable=False),
        sa.Column("status", sa.String(length=24), server_default="OPEN", nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("booking_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_to_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("category IN ('PAYMENT', 'DEFECT', 'DOCUMENT', 'GENERAL')", name=op.f("ck_tickets_category")),
        sa.CheckConstraint("priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')", name=op.f("ck_tickets_priority")),
        sa.CheckConstraint("status IN ('OPEN', 'IN_PROGRESS', 'WAITING_ON_CUSTOMER', 'RESOLVED', 'CLOSED')", name=op.f("ck_tickets_status")),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["users.id"], name=op.f("fk_tickets_assigned_to_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["booking_id"], ["sale_bookings.id"], name=op.f("fk_tickets_booking_id_sale_bookings"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_tickets_contact_id_contacts"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name=op.f("fk_tickets_created_by_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_tickets_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tickets")),
        sa.UniqueConstraint("tenant_id", "ticket_number", name="uq_tickets_tenant_number"),
    )
    op.create_index(op.f("ix_tickets_assigned_to_id"), "tickets", ["assigned_to_id"], unique=False)
    op.create_index(op.f("ix_tickets_tenant_id"), "tickets", ["tenant_id"], unique=False)
    op.create_index("ix_tickets_tenant_status", "tickets", ["tenant_id", "status"], unique=False)
    op.create_index("ix_tickets_tenant_sla_due_at", "tickets", ["tenant_id", "sla_due_at"], unique=False)

    op.create_table(
        "ticket_comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("length(trim(body)) BETWEEN 1 AND 4000", name=op.f("ck_ticket_comments_body")),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], name=op.f("fk_ticket_comments_author_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], name=op.f("fk_ticket_comments_ticket_id_tickets"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_ticket_comments_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ticket_comments")),
    )
    op.create_index(op.f("ix_ticket_comments_ticket_id"), "ticket_comments", ["ticket_id"], unique=False)
    op.create_index(op.f("ix_ticket_comments_tenant_id"), "ticket_comments", ["tenant_id"], unique=False)
    op.create_index("ix_ticket_comments_tenant_ticket_created", "ticket_comments", ["tenant_id", "ticket_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ticket_comments_tenant_ticket_created", table_name="ticket_comments")
    op.drop_index(op.f("ix_ticket_comments_tenant_id"), table_name="ticket_comments")
    op.drop_index("ix_ticket_comments_tenant_id_id", table_name="ticket_comments")
    op.drop_index(op.f("ix_ticket_comments_ticket_id"), table_name="ticket_comments")
    op.drop_table("ticket_comments")

    op.drop_index("ix_tickets_tenant_sla_due_at", table_name="tickets")
    op.drop_index("ix_tickets_tenant_status", table_name="tickets")
    op.drop_index(op.f("ix_tickets_tenant_id"), table_name="tickets")
    op.drop_index("ix_tickets_tenant_id_id", table_name="tickets")
    op.drop_index(op.f("ix_tickets_assigned_to_id"), table_name="tickets")
    op.drop_table("tickets")
