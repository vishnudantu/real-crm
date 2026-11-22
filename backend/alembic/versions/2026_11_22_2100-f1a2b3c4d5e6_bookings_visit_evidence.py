"""bookings: staff site-visit evidence artifacts

Revision ID: f1a2b3c4d5e6
Revises: c4d5e6f7a8b9
Create Date: 2026-11-22 21:00:00

Staff-uploaded proof of a site visit (photo/pdf metadata + notes) with a
verification lifecycle (SUBMITTED/VERIFIED/REJECTED). Binary content lives in
local storage; this table holds metadata + sha256 for integrity.

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Composite tenant_id_id index is auto-emitted by app.db.tenancy's
    # after_parent_attach listener, not created here.
    op.create_table(
        "visit_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="SUBMITTED", nullable=False),
        sa.Column("uploaded_by_id", sa.Uuid(), nullable=True),
        sa.Column("verified_by_id", sa.Uuid(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("status IN ('SUBMITTED','VERIFIED','REJECTED')", name=op.f("ck_visit_evidence_status")),
        sa.CheckConstraint("length(content_sha256) = 64", name=op.f("ck_visit_evidence_sha256")),
        sa.CheckConstraint("size_bytes >= 0", name=op.f("ck_visit_evidence_size_non_negative")),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], name=op.f("fk_visit_evidence_booking_id_bookings"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_visit_evidence_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], name=op.f("fk_visit_evidence_uploaded_by_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["verified_by_id"], ["users.id"], name=op.f("fk_visit_evidence_verified_by_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visit_evidence")),
    )
    op.create_index(op.f("ix_visit_evidence_booking_id"), "visit_evidence", ["booking_id"], unique=False)
    op.create_index(op.f("ix_visit_evidence_tenant_id"), "visit_evidence", ["tenant_id"], unique=False)
    op.create_index("ix_visit_evidence_booking", "visit_evidence", ["booking_id"], unique=False)
    op.create_index("ix_visit_evidence_tenant_status", "visit_evidence", ["tenant_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_visit_evidence_tenant_status", table_name="visit_evidence")
    op.drop_index("ix_visit_evidence_booking", table_name="visit_evidence")
    op.drop_index(op.f("ix_visit_evidence_tenant_id"), table_name="visit_evidence")
    op.drop_index("ix_visit_evidence_tenant_id_id", table_name="visit_evidence")
    op.drop_index(op.f("ix_visit_evidence_booking_id"), table_name="visit_evidence")
    op.drop_table("visit_evidence")
