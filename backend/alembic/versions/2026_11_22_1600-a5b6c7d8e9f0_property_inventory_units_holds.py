"""property inventory: canonical units, availability state machine, atomic holds

Revision ID: a5b6c7d8e9f0
Revises: f2a3b4c5d6e7
Create Date: 2026-11-22 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a5b6c7d8e9f0"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Composite tenant_id_id indexes are auto-emitted by app.db.tenancy's
    # after_parent_attach listener, not created here.
    op.create_table(
        "property_units",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("internal_code", sa.String(length=64), nullable=False),
        sa.Column("configuration", sa.String(length=100), nullable=True),
        sa.Column("floor", sa.String(length=64), nullable=True),
        sa.Column("position", sa.String(length=64), nullable=True),
        sa.Column("tower", sa.String(length=64), nullable=True),
        sa.Column("carpet_area_sqft", sa.Integer(), nullable=True),
        sa.Column("built_up_area_sqft", sa.Integer(), nullable=True),
        sa.Column("plot_number", sa.String(length=64), nullable=True),
        sa.Column("facing", sa.String(length=64), nullable=True),
        sa.Column("views", sa.String(length=255), nullable=True),
        sa.Column("saleable", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="DRAFT", nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("rera_disclosure_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("built_up_area_sqft IS NULL OR built_up_area_sqft > 0", name=op.f("ck_property_units_built_up_area_positive")),
        sa.CheckConstraint("carpet_area_sqft IS NULL OR carpet_area_sqft > 0", name=op.f("ck_property_units_carpet_area_positive")),
        sa.CheckConstraint("status IN ('DRAFT', 'APPROVED', 'AVAILABLE', 'ON_HOLD', 'RESERVED', 'BOOKED', 'SOLD', 'BLOCKED', 'UNDER_DISPUTE', 'CANCELLED')", name=op.f("ck_property_units_unit_status_valid")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_property_units_project_id_projects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_property_units_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_property_units")),
        sa.UniqueConstraint("tenant_id", "project_id", "internal_code", name="uq_property_units_tenant_project_code"),
    )
    op.create_index(op.f("ix_property_units_project_id"), "property_units", ["project_id"], unique=False)
    op.create_index(op.f("ix_property_units_tenant_id"), "property_units", ["tenant_id"], unique=False)
    op.create_index("ix_property_units_tenant_status", "property_units", ["tenant_id", "status"], unique=False)

    op.create_table(
        "unit_status_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=24), nullable=False),
        sa.Column("to_status", sa.String(length=24), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("from_status IN ('DRAFT', 'APPROVED', 'AVAILABLE', 'ON_HOLD', 'RESERVED', 'BOOKED', 'SOLD', 'BLOCKED', 'UNDER_DISPUTE', 'CANCELLED')", name=op.f("ck_unit_status_events_event_from_status_valid")),
        sa.CheckConstraint("to_status IN ('DRAFT', 'APPROVED', 'AVAILABLE', 'ON_HOLD', 'RESERVED', 'BOOKED', 'SOLD', 'BLOCKED', 'UNDER_DISPUTE', 'CANCELLED')", name=op.f("ck_unit_status_events_event_to_status_valid")),
        sa.CheckConstraint("source IN ('MANUAL', 'HOLD', 'BOOKING', 'CANCELLATION')", name=op.f("ck_unit_status_events_event_source_valid")),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name=op.f("fk_unit_status_events_actor_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_unit_status_events_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["unit_id"], ["property_units.id"], name=op.f("fk_unit_status_events_unit_id_property_units"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_unit_status_events")),
    )
    op.create_index("ix_unit_status_events_unit_effective", "unit_status_events", ["unit_id", "effective_at"], unique=False)
    op.create_index(op.f("ix_unit_status_events_unit_id"), "unit_status_events", ["unit_id"], unique=False)
    op.create_index(op.f("ix_unit_status_events_tenant_id"), "unit_status_events", ["tenant_id"], unique=False)

    op.create_table(
        "unit_holds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("unit_id", sa.Uuid(), nullable=False),
        sa.Column("opportunity_ref", sa.String(length=128), nullable=True),
        sa.Column("lead_id", sa.Uuid(), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=16), server_default="ACTIVE", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extension_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("converted_booking_id", sa.Uuid(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_source", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("extension_count >= 0 AND extension_count <= 2", name=op.f("ck_unit_holds_hold_extension_policy")),
        sa.CheckConstraint("release_source IS NULL OR release_source IN ('EXPIRY','MANUAL','CONVERTED','CANCELLED')", name=op.f("ck_unit_holds_hold_release_source_valid")),
        sa.CheckConstraint("state IN ('ACTIVE', 'EXPIRED', 'CONVERTED', 'RELEASED', 'CANCELLED')", name=op.f("ck_unit_holds_hold_state_valid")),
        sa.ForeignKeyConstraint(["converted_booking_id"], ["sale_bookings.id"], name=op.f("fk_unit_holds_converted_booking_id_sale_bookings"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], name=op.f("fk_unit_holds_lead_id_leads"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_unit_holds_owner_user_id_users"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_unit_holds_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["unit_id"], ["property_units.id"], name=op.f("fk_unit_holds_unit_id_property_units"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_unit_holds")),
    )
    op.create_index(op.f("ix_unit_holds_unit_id"), "unit_holds", ["unit_id"], unique=False)
    op.create_index(op.f("ix_unit_holds_tenant_id"), "unit_holds", ["tenant_id"], unique=False)
    op.create_index("ix_unit_holds_tenant_expiry", "unit_holds", ["tenant_id", "state", "expires_at"], unique=False)
    op.create_index(
        "uq_unit_holds_one_active_per_unit", "unit_holds", ["tenant_id", "unit_id"], unique=True,
        sqlite_where=sa.text("state = 'ACTIVE'"), postgresql_where=sa.text("state = 'ACTIVE'"),  # matches model's partial index predicate
    )

    # Batch mode keeps this valid on SQLite (copy-and-move) while emitting
    # plain ALTER TABLE on PostgreSQL.
    with op.batch_alter_table("sale_bookings") as batch_op:
        batch_op.add_column(sa.Column("unit_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_sale_bookings_unit_id_property_units"),
            "property_units", ["unit_id"], ["id"], ondelete="SET NULL",
        )
        batch_op.create_index(op.f("ix_sale_bookings_unit_id"), ["unit_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("sale_bookings") as batch_op:
        batch_op.drop_index(op.f("ix_sale_bookings_unit_id"))
        batch_op.drop_constraint(op.f("fk_sale_bookings_unit_id_property_units"), type_="foreignkey")
        batch_op.drop_column("unit_id")

    op.drop_index("uq_unit_holds_one_active_per_unit", table_name="unit_holds")
    op.drop_index("ix_unit_holds_tenant_expiry", table_name="unit_holds")
    op.drop_index(op.f("ix_unit_holds_tenant_id"), table_name="unit_holds")
    op.drop_index("ix_unit_holds_tenant_id_id", table_name="unit_holds")
    op.drop_index(op.f("ix_unit_holds_unit_id"), table_name="unit_holds")
    op.drop_table("unit_holds")

    op.drop_index(op.f("ix_unit_status_events_tenant_id"), table_name="unit_status_events")
    op.drop_index("ix_unit_status_events_tenant_id_id", table_name="unit_status_events")
    op.drop_index(op.f("ix_unit_status_events_unit_id"), table_name="unit_status_events")
    op.drop_index("ix_unit_status_events_unit_effective", table_name="unit_status_events")
    op.drop_table("unit_status_events")

    op.drop_index("ix_property_units_tenant_status", table_name="property_units")
    op.drop_index(op.f("ix_property_units_tenant_id"), table_name="property_units")
    op.drop_index("ix_property_units_tenant_id_id", table_name="property_units")
    op.drop_index(op.f("ix_property_units_project_id"), table_name="property_units")
    op.drop_table("property_units")
