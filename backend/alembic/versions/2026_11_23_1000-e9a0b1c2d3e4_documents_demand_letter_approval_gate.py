"""documents: demand-letter approval gate columns (P0.3)

Revision ID: e9a0b1c2d3e4
Revises: e7f8a9b0c1d2
Create Date: 2026-11-23 10:00:00

Adds the delivery-gate lifecycle to documents:

- ``review_state`` defaults to 'APPROVED' so every pre-existing document keeps
  behaving as already-approved; the prepare flow writes 'PENDING_REVIEW' and
  an admin release writes 'APPROVED_FOR_SEND' (or 'VOIDED' on rejection).
- ``approved_by`` / ``approved_at`` record who released the letter for send.

Existing rows are backfilled in batch mode, which is SQLite-safe (table
rebuild) and a no-op metadata change on PostgreSQL.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e9a0b1c2d3e4"
down_revision: Union[str, None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_REVIEW_STATE_CHECK = (
    "review_state IN ('PENDING_REVIEW','APPROVED_FOR_SEND','APPROVED','VOIDED')"
)


def upgrade() -> None:
    """Add the approval-gate columns with the approved-by default."""
    with op.batch_alter_table("documents") as batch:
        batch.add_column(
            sa.Column(
                "review_state",
                sa.String(length=24),
                nullable=False,
                server_default="APPROVED",
            )
        )
        batch.add_column(sa.Column("approved_by", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint("document_review_state_valid", _REVIEW_STATE_CHECK)
        # Inside the batch: SQLite can only add FK constraints during a rebuild.
        batch.create_foreign_key(
            "fk_documents_approved_by_users", "users", ["approved_by"], ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_documents_tenant_review_state", "documents", ["tenant_id", "review_state"]
    )


def downgrade() -> None:
    """Remove the gate columns, restoring the pre-P0.3 document shape."""
    op.drop_index("ix_documents_tenant_review_state", table_name="documents")
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("fk_documents_approved_by_users", type_="foreignkey")
        batch.drop_constraint("document_review_state_valid", type_="check")
        batch.drop_column("approved_at")
        batch.drop_column("approved_by")
        batch.drop_column("review_state")
