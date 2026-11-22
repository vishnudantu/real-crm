"""connect_dialer: dispositions, DNC suppression, scheduled callbacks

Revision ID: e5f6a7b8c9d0
Revises: f7a8b9c0d1e2
Create Date: 2026-11-23 00:00:00

Contact-centre controls layered on the existing omnichannel calling: a
disposition per call, a per-tenant Do-Not-Call list, and scheduled callbacks
with assignment. No change to the telephony provider itself.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "call_dispositions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("call_id", sa.Uuid(), nullable=False),
        sa.Column("disposition", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("disposition IN ('INTERESTED','NOT_INTERESTED','VISIT_CONFIRMED','CALL_BACK','WRONG_NUMBER','PAYMENT_DISCUSSION','ESCALATION','NO_ANSWER')", name=op.f("ck_call_dispositions_value")),
        sa.ForeignKeyConstraint(["call_id"], ["call_records.id"], name=op.f("fk_call_dispositions_call_id_call_records"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["users.id"], name=op.f("fk_call_dispositions_recorded_by_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_call_dispositions_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_call_dispositions")),
        sa.UniqueConstraint("tenant_id", "call_id", name="uq_call_dispositions_call"),
    )
    op.create_index(op.f("ix_call_dispositions_call_id"), "call_dispositions", ["call_id"], unique=False)
    op.create_index(op.f("ix_call_dispositions_tenant_id"), "call_dispositions", ["tenant_id"], unique=False)
    op.create_index("ix_call_dispositions_tenant_created", "call_dispositions", ["tenant_id", "created_at"], unique=False)

    op.create_table(
        "do_not_call_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("phone_number", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("added_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["added_by_id"], ["users.id"], name=op.f("fk_do_not_call_entries_added_by_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_do_not_call_entries_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_do_not_call_entries")),
        sa.UniqueConstraint("tenant_id", "phone_number", name="uq_do_not_call_tenant_phone"),
    )
    op.create_index(op.f("ix_do_not_call_entries_tenant_id"), "do_not_call_entries", ["tenant_id"], unique=False)
    op.create_index("ix_do_not_call_tenant_phone", "do_not_call_entries", ["tenant_id", "phone_number"], unique=False)

    op.create_table(
        "scheduled_callbacks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=True),
        sa.Column("call_id", sa.Uuid(), nullable=True),
        sa.Column("phone_number", sa.String(length=32), nullable=False),
        sa.Column("assigned_to_id", sa.Uuid(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="SCHEDULED", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("status IN ('SCHEDULED','DONE','CANCELLED')", name=op.f("ck_scheduled_callbacks_status")),
        sa.ForeignKeyConstraint(["assigned_to_id"], ["users.id"], name=op.f("fk_scheduled_callbacks_assigned_to_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["call_id"], ["call_records.id"], name=op.f("fk_scheduled_callbacks_call_id_call_records"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name=op.f("fk_scheduled_callbacks_created_by_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], name=op.f("fk_scheduled_callbacks_lead_id_leads"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_scheduled_callbacks_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scheduled_callbacks")),
    )
    op.create_index(op.f("ix_scheduled_callbacks_assigned_to_id"), "scheduled_callbacks", ["assigned_to_id"], unique=False)
    op.create_index(op.f("ix_scheduled_callbacks_lead_id"), "scheduled_callbacks", ["lead_id"], unique=False)
    op.create_index(op.f("ix_scheduled_callbacks_tenant_id"), "scheduled_callbacks", ["tenant_id"], unique=False)
    op.create_index("ix_scheduled_callbacks_tenant_status_time", "scheduled_callbacks", ["tenant_id", "status", "scheduled_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scheduled_callbacks_tenant_status_time", table_name="scheduled_callbacks")
    op.drop_index(op.f("ix_scheduled_callbacks_tenant_id"), table_name="scheduled_callbacks")
    op.drop_index("ix_scheduled_callbacks_tenant_id_id", table_name="scheduled_callbacks")
    op.drop_index(op.f("ix_scheduled_callbacks_lead_id"), table_name="scheduled_callbacks")
    op.drop_index(op.f("ix_scheduled_callbacks_assigned_to_id"), table_name="scheduled_callbacks")
    op.drop_table("scheduled_callbacks")

    op.drop_index("ix_do_not_call_tenant_phone", table_name="do_not_call_entries")
    op.drop_index(op.f("ix_do_not_call_entries_tenant_id"), table_name="do_not_call_entries")
    op.drop_index("ix_do_not_call_entries_tenant_id_id", table_name="do_not_call_entries")
    op.drop_table("do_not_call_entries")

    op.drop_index("ix_call_dispositions_tenant_created", table_name="call_dispositions")
    op.drop_index(op.f("ix_call_dispositions_tenant_id"), table_name="call_dispositions")
    op.drop_index("ix_call_dispositions_tenant_id_id", table_name="call_dispositions")
    op.drop_index(op.f("ix_call_dispositions_call_id"), table_name="call_dispositions")
    op.drop_table("call_dispositions")
