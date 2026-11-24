"""city_intel: curated project amenities + source-verified locality reports

Revision ID: c7a1f2d4e8b9
Revises: 4b8d2f6c91ae
Create Date: 2026-11-24 10:00:00

Phase 1 of the City Intelligence Engine (Module 22). Adds two tenant-owned
tables for admin-curated, source-attributed locality input. No external feed,
no geocoding. Idempotent and SQLite batch-safe. The composite
ix_<table>_tenant_id_id index is auto-emitted by app.db.tenancy's
after_parent_attach listener and is intentionally NOT created here.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7a1f2d4e8b9"
down_revision: Union[str, None] = "4b8d2f6c91ae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(inspector, name: str) -> bool:
    return name in inspector.get_table_names()


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not _has_table(inspector, "project_amenities"):
        op.create_table(
            "project_amenities",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("category", sa.String(length=24), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("distance_km", sa.Float(), nullable=False, server_default="0"),
            sa.Column("travel_minutes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("source_ref", sa.String(length=500), nullable=True),
            sa.Column("confidence", sa.String(length=16), server_default="estimated", nullable=False),
            sa.Column("as_of", sa.Date(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.CheckConstraint("category IN ('school','hospital','transit','employment','amenity')", name=op.f("ck_project_amenities_amenity_category_valid")),
            sa.CheckConstraint("distance_km >= 0", name=op.f("ck_project_amenities_amenity_distance_non_negative")),
            sa.CheckConstraint("travel_minutes >= 0", name=op.f("ck_project_amenities_amenity_travel_non_negative")),
            sa.CheckConstraint("confidence IN ('verified','estimated','unverified')", name=op.f("ck_project_amenities_amenity_confidence_valid")),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_project_amenities_project_id_projects"), ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_project_amenities_tenant_id_tenants"), ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_project_amenities")),
        )
        op.create_index(op.f("ix_project_amenities_project_id"), "project_amenities", ["project_id"], unique=False)
        op.create_index(op.f("ix_project_amenities_tenant_id"), "project_amenities", ["tenant_id"], unique=False)
        op.create_index("ix_project_amenities_tenant_project", "project_amenities", ["tenant_id", "project_id"], unique=False)

    if not _has_table(inspector, "locality_reports"):
        op.create_table(
            "locality_reports",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("sources", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=16), server_default="DRAFT", nullable=False),
            sa.Column("as_of", sa.Date(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.CheckConstraint("status IN ('DRAFT','APPROVED')", name=op.f("ck_locality_reports_locality_report_status_valid")),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_locality_reports_project_id_projects"), ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_locality_reports_tenant_id_tenants"), ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_locality_reports")),
            sa.UniqueConstraint("tenant_id", "project_id", "title", name="uq_locality_reports_tenant_project_title"),
        )
        op.create_index(op.f("ix_locality_reports_project_id"), "locality_reports", ["project_id"], unique=False)
        op.create_index(op.f("ix_locality_reports_tenant_id"), "locality_reports", ["tenant_id"], unique=False)
        op.create_index("ix_locality_reports_tenant_project", "locality_reports", ["tenant_id", "project_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_locality_reports_tenant_project", table_name="locality_reports")
    op.drop_index(op.f("ix_locality_reports_tenant_id"), table_name="locality_reports")
    op.drop_index(op.f("ix_locality_reports_project_id"), table_name="locality_reports")
    op.drop_table("locality_reports")

    op.drop_index("ix_project_amenities_tenant_project", table_name="project_amenities")
    op.drop_index(op.f("ix_project_amenities_tenant_id"), table_name="project_amenities")
    op.drop_index(op.f("ix_project_amenities_project_id"), table_name="project_amenities")
    op.drop_table("project_amenities")
