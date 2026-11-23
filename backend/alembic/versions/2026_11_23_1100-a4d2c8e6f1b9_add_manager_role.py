"""add sales/inventory manager role

Revision ID: a4d2c8e6f1b9
Revises: b9c0d1e2f3a4
Create Date: 2026-11-23 11:00:00

Existing databases need the new role row independently of application startup.
The insert is conditional so re-running this data migration is safe. The
built-in role is retained on downgrade because user rows may reference it.
"""

from __future__ import annotations

from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4d2c8e6f1b9"
down_revision: Union[str, None] = "b9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT 1 FROM roles WHERE name = 'MANAGER'")) is None:
        roles = sa.table(
            "roles",
            sa.column("id", sa.Uuid()),
            sa.column("name", sa.String()),
            sa.column("description", sa.String()),
        )
        op.bulk_insert(
            roles,
            [
                {
                    "id": uuid4(),
                    "name": "MANAGER",
                    "description": "Sales/inventory manager",
                }
            ],
        )


def downgrade() -> None:
    """Keep MANAGER to avoid orphaning users assigned the built-in role."""
