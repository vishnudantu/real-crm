"""projects.project_type: additive inventory authoring taxonomy

Revision ID: e2b7c4a9d1f6
Revises: c3a7f1d9e2b5
Create Date: 2026-11-23 12:00:00

Nullable so every existing project keeps its current behavior. The CHECK
permits NULL and the five supported values; batch mode keeps this valid on
SQLite as well as PostgreSQL. Both directions are guarded, so a re-run against
a partially migrated database is harmless.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e2b7c4a9d1f6"
down_revision: Union[str, None] = "d4e6a8b2c1f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT_NAME = "project_type_valid"
_PROJECT_TYPES = ("APARTMENT", "VILLA", "PLOT", "COMMERCIAL", "MIXED")


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def _has_constraint(inspector, table: str, name: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    checks = inspector.get_check_constraints(table)
    return name in {c.get("name") for c in checks}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    values = ", ".join(f"'{value}'" for value in _PROJECT_TYPES)
    add_constraint = not _has_constraint(inspector, "projects", _CONSTRAINT_NAME)
    add_column = not _has_column(inspector, "projects", "project_type")
    if not add_column and not add_constraint:
        return
    with op.batch_alter_table("projects") as batch_op:
        if add_column:
            batch_op.add_column(sa.Column("project_type", sa.String(length=16), nullable=True))
        if add_constraint:
            batch_op.create_check_constraint(
                _CONSTRAINT_NAME,
                f"project_type IS NULL OR project_type IN ({values})",
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    drop_constraint = _has_constraint(inspector, "projects", _CONSTRAINT_NAME)
    drop_column = _has_column(inspector, "projects", "project_type")
    if not drop_column and not drop_constraint:
        return
    with op.batch_alter_table("projects") as batch_op:
        if drop_constraint:
            batch_op.drop_constraint(_CONSTRAINT_NAME, type_="check")
        if drop_column:
            batch_op.drop_column("project_type")
