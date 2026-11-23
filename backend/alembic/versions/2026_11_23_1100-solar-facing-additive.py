"""solar: project coordinates, tower orientations, unit facing_deg

Revision ID: c3a7f1d9e2b5
Revises: a4d2c8e6f1b9
Create Date: 2026-11-23 11:00:00

Additive changes only:
- projects.latitude (Float, nullable)
- projects.longitude (Float, nullable)
- property_units.facing_deg (Float, nullable)
- new table: tower_orientations (tenant-scoped, unique per tenant+project+tower)

Batch mode keeps the ALTER TABLE valid on SQLite (copy-and-move) while
emitting plain ALTER TABLE on PostgreSQL.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3a7f1d9e2b5"
down_revision: Union[str, None] = "a4d2c8e6f1b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table: str, column: str) -> bool:
    if table not in inspector.get_table_names():
        return False
    return column in {c["name"] for c in inspector.get_columns(table)}


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    inspector = sa.inspect(op.get_bind())
    if not _has_column(inspector, table, column.name):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(column)


def upgrade() -> None:
    # 1. Add latitude/longitude to projects.
    _add_column_if_missing(
        "projects",
        sa.Column("latitude", sa.Float(), nullable=True),
    )
    _add_column_if_missing(
        "projects",
        sa.Column("longitude", sa.Float(), nullable=True),
    )

    # 2. Add facing_deg to property_units.
    _add_column_if_missing(
        "property_units",
        sa.Column("facing_deg", sa.Float(), nullable=True),
    )

    # 3. Create tower_orientations table.
    inspector = sa.inspect(op.get_bind())
    if "tower_orientations" not in inspector.get_table_names():
        op.create_table(
            "tower_orientations",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("tower_label", sa.String(length=64), nullable=False),
            sa.Column("orientation_deg", sa.Float(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.CheckConstraint(
                "orientation_deg >= 0 AND orientation_deg < 360",
                name=op.f("ck_tower_orientations_tower_orientation_range"),
            ),
            sa.ForeignKeyConstraint(
                ["project_id"], ["projects.id"],
                name=op.f("fk_tower_orientations_project_id_projects"),
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name=op.f("fk_tower_orientations_tenant_id_tenants"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_tower_orientations")),
            sa.UniqueConstraint(
                "tenant_id", "project_id", "tower_label",
                name="uq_tower_orientations_tenant_project_tower",
            ),
        )
        op.create_index(
            op.f("ix_tower_orientations_project_id"),
            "tower_orientations", ["project_id"], unique=False,
        )
        op.create_index(
            op.f("ix_tower_orientations_tenant_id"),
            "tower_orientations", ["tenant_id"], unique=False,
        )
        op.create_index(
            "ix_tower_orientations_tenant_project",
            "tower_orientations", ["tenant_id", "project_id"], unique=False,
        )
        # NOTE: ix_tower_orientations_tenant_id_id is intentionally NOT created
        # here — the after_parent_attach listener in app.db.tenancy auto-emits
        # that composite index when the table is built from ORM metadata, so
        # creating it explicitly raises "index already exists".


def downgrade() -> None:
    op.drop_index(
        "ix_tower_orientations_tenant_id_id",
        table_name="tower_orientations",
    )
    op.drop_index(
        "ix_tower_orientations_tenant_project",
        table_name="tower_orientations",
    )
    op.drop_index(
        op.f("ix_tower_orientations_tenant_id"),
        table_name="tower_orientations",
    )
    op.drop_index(
        op.f("ix_tower_orientations_project_id"),
        table_name="tower_orientations",
    )
    op.drop_table("tower_orientations")

    with op.batch_alter_table("property_units") as batch_op:
        batch_op.drop_column("facing_deg")

    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("longitude")
        batch_op.drop_column("latitude")
