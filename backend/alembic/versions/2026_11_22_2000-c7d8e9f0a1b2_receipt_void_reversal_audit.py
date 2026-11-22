"""receipt void/reversal audit metadata

Revision ID: c7d8e9f0a1b2
Revises: b4c5d6e7f8a9
Create Date: 2026-11-22 20:00:00

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("receipts", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("receipts", sa.Column("voided_by_id", sa.Uuid(), nullable=True))
    op.add_column("receipts", sa.Column("void_reason", sa.Text(), nullable=True))
    op.create_foreign_key(
        op.f("fk_receipts_voided_by_id_users"),
        "receipts",
        "users",
        ["voided_by_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_receipts_voided_by_id_users"), "receipts", type_="foreignkey")
    op.drop_column("receipts", "void_reason")
    op.drop_column("receipts", "voided_by_id")
    op.drop_column("receipts", "voided_at")
