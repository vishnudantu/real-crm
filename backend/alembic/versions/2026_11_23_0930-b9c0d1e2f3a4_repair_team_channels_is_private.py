"""repair: ensure team_channels.is_private exists

Revision ID: b9c0d1e2f3a4
Revises: c8d9e0f1a2b3
Create Date: 2026-11-23 09:30:00

The dev SQLite database was migrated to head before ``is_private`` was added to
the TeamChannel ORM model, so the column-add inside d6e7f8a9b0c1 had already
no-op'd and Alembic will not re-run it. The ORM now always selects
``is_private``, which raises ``sqlite3.OperationalError: no such column`` on
every team-chat read (surfaced as HTTP 500 on /teamchat/channels).

This repair is idempotent: it adds ``is_private`` only when the table exists and
the column is missing, so already-correct databases (fresh installs, CI) are
untouched. Batch mode keeps the ALTER valid on SQLite and a plain ALTER on
PostgreSQL.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b9c0d1e2f3a4"
down_revision: Union[str, None] = "c8d9e0f1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "team_channels" in inspector.get_table_names() and not _has_column(
        inspector, "team_channels", "is_private"
    ):
        with op.batch_alter_table("team_channels") as batch_op:
            batch_op.add_column(
                sa.Column("is_private", sa.Boolean(), server_default="false", nullable=False)
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if _has_column(inspector, "team_channels", "is_private"):
        with op.batch_alter_table("team_channels") as batch_op:
            batch_op.drop_column("is_private")
