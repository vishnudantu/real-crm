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
    """Allow an encrypted, short-lived account selection before project routing."""
    op.add_column(
        "integration_connections",
        sa.Column("connection_status", sa.String(length=24), server_default="ACTIVE", nullable=False),
    )
    op.add_column(
        "integration_connections",
        sa.Column("pending_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("integration_connections", "project_id", nullable=True)


def downgrade() -> None:
    op.alter_column("integration_connections", "project_id", nullable=False)
    op.drop_column("integration_connections", "pending_expires_at")
    op.drop_column("integration_connections", "connection_status")
