"""guided ad-provider OAuth connections

Revision ID: c6d7e8f9a0b1
Revises: b4c5d6e7f8a9
Create Date: 2026-11-22 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow an encrypted, short-lived account selection before project routing.

    Idempotent: a partially applied prior run may have created some columns.
    """
    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(op.get_bind())
    existing_columns = {col["name"] for col in inspector.get_columns("integration_connections")}
    if "connection_status" not in existing_columns:
        op.add_column(
            "integration_connections",
            sa.Column("connection_status", sa.String(length=24), server_default="ACTIVE", nullable=False),
        )
    if "pending_expires_at" not in existing_columns:
        op.add_column(
            "integration_connections",
            sa.Column("pending_expires_at", sa.DateTime(timezone=True), nullable=True),
        )
    # SQLite cannot ALTER COLUMN DROP NOT NULL directly; batch mode performs the
    # safe copy-and-move. PostgreSQL accepts it identically.
    with op.batch_alter_table("integration_connections") as batch_op:
        batch_op.alter_column("project_id", nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("integration_connections") as batch_op:
        batch_op.alter_column("project_id", nullable=False)
    op.drop_column("integration_connections", "pending_expires_at")
    op.drop_column("integration_connections", "connection_status")
