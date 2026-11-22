"""receipt void/reversal audit metadata

Revision ID: c7d8e9f0a1b2
Revises: d5e6f7a8b9c0
Create Date: 2026-11-22 20:00:00

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: a partially applied earlier attempt may have added columns.
    inspector = sa.inspect(op.get_bind())
    existing = {col["name"] for col in inspector.get_columns("receipts")}
    if "voided_at" not in existing:
        op.add_column("receipts", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
    if "voided_by_id" not in existing:
        op.add_column("receipts", sa.Column("voided_by_id", sa.Uuid(), nullable=True))
    if "void_reason" not in existing:
        op.add_column("receipts", sa.Column("void_reason", sa.Text(), nullable=True))
    # SQLite does not support ADD CONSTRAINT via ALTER; use copy-and-move batch mode.
    with op.batch_alter_table("receipts") as batch_op:
        batch_op.create_foreign_key(
            op.f("fk_receipts_voided_by_id_users"),
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
