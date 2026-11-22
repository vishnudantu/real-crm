"""construction: milestones + progress updates with certification gate

Revision ID: c3d4e5f6a7b9
Revises: f7a8b9c0d1e2
Create Date: 2026-11-23 09:00:00

NOTE: the task spec requested revision id ``c3d4e5f6a7b8``, but that id is
already used by the existing ``create_follow_ups`` migration on the
consolidation base. Reusing it would corrupt the Alembic revision graph, so a
genuinely unique id (``c3d4e5f6a7b9``) is used instead; the authoritative
``down_revision`` (``f7a8b9c0d1e2``) is preserved as required.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b9"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create construction_milestones + milestone_updates tables.

    The composite (tenant_id, id) indexes are auto-emitted by app.db.tenancy's
    after_parent_attach listener, so they are intentionally absent here.
    """
    op.create_table(
        "construction_milestones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column("actual_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="NOT_STARTED", nullable=False),
        sa.Column("percent_complete", sa.Integer(), server_default="0", nullable=False),
        sa.Column("evidence_notes", sa.Text(), nullable=True),
        sa.Column("certified_by_id", sa.Uuid(), nullable=True),
        sa.Column("certified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "percent_complete BETWEEN 0 AND 100",
            name=op.f("ck_construction_milestones_percent_complete_range"),
        ),
        sa.CheckConstraint(
            "status IN ('NOT_STARTED','IN_PROGRESS','COMPLETED','DELAYED','CERTIFIED')",
            name=op.f("ck_construction_milestones_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name=op.f("fk_construction_milestones_project_id_projects"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["certified_by_id"], ["users.id"],
            name=op.f("fk_construction_milestones_certified_by_id_users"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_construction_milestones_tenant_id_tenants"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_milestones")),
        sa.UniqueConstraint(
            "tenant_id", "project_id", "sequence_no",
            name="uq_construction_milestones_tenant_project_sequence",
        ),
    )
    op.create_index(op.f("ix_construction_milestones_project_id"), "construction_milestones", ["project_id"], unique=False)
    op.create_index(op.f("ix_construction_milestones_tenant_id"), "construction_milestones", ["tenant_id"], unique=False)
    op.create_index(
        "ix_construction_milestones_tenant_project_status",
        "construction_milestones", ["tenant_id", "project_id", "status"], unique=False,
    )

    op.create_table(
        "milestone_updates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("milestone_id", sa.Uuid(), nullable=False),
        sa.Column("percent_complete", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "percent_complete BETWEEN 0 AND 100",
            name=op.f("ck_milestone_updates_percent_complete_range"),
        ),
        sa.ForeignKeyConstraint(
            ["milestone_id"], ["construction_milestones.id"],
            name=op.f("fk_milestone_updates_milestone_id_construction_milestones"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"],
            name=op.f("fk_milestone_updates_author_id_users"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_milestone_updates_tenant_id_tenants"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_milestone_updates")),
    )
    op.create_index(op.f("ix_milestone_updates_milestone_id"), "milestone_updates", ["milestone_id"], unique=False)
    op.create_index(op.f("ix_milestone_updates_tenant_id"), "milestone_updates", ["tenant_id"], unique=False)


def downgrade() -> None:
    """Drop both tables plus the auto-emitted composite indexes."""
    op.drop_index(op.f("ix_milestone_updates_tenant_id"), table_name="milestone_updates")
    op.drop_index(op.f("ix_milestone_updates_milestone_id"), table_name="milestone_updates")
    op.drop_index("ix_milestone_updates_tenant_id_id", table_name="milestone_updates")
    op.drop_table("milestone_updates")

    op.drop_index("ix_construction_milestones_tenant_project_status", table_name="construction_milestones")
    op.drop_index(op.f("ix_construction_milestones_tenant_id"), table_name="construction_milestones")
    op.drop_index(op.f("ix_construction_milestones_project_id"), table_name="construction_milestones")
    op.drop_index("ix_construction_milestones_tenant_id_id", table_name="construction_milestones")
    op.drop_table("construction_milestones")
