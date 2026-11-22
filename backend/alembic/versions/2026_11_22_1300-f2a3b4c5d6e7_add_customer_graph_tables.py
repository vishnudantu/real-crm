"""add customer graph tables (contacts, contact_methods, opportunities, contact_merges)

Revision ID: f2a3b4c5d6e7
Revises: a3b4c5d6e7f8
Create Date: 2026-11-22 13:00:00

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the customer graph tables.

    Composite tenant_id_id indexes are auto-emitted by app.db.tenancy's
    after_parent_attach listener during create_table, so they are NOT created
    explicitly here (mirrors tenant_features / integration_connections).
    """
    op.create_table(
        "contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("canonical_key", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("primary_language", sa.String(length=8), server_default="en", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="ACTIVE", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("merged_into_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["merged_into_id"], ["contacts.id"], name=op.f("fk_contacts_merged_into_id_contacts"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_contacts_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
        sa.UniqueConstraint("tenant_id", "canonical_key", name="uq_contacts_tenant_canonical_key"),
        sa.CheckConstraint("status IN ('ACTIVE','MERGED','ANONYMIZED')", name="ck_contacts_status"),
    )
    op.create_index(op.f("ix_contacts_status"), "contacts", ["status"], unique=False)
    op.create_index(op.f("ix_contacts_tenant_id"), "contacts", ["tenant_id"], unique=False)
    op.create_index("ix_contacts_tenant_status", "contacts", ["tenant_id", "status"], unique=False)

    op.create_table(
        "contact_methods",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("value", sa.String(length=320), nullable=False),
        sa.Column("normalized_value", sa.String(length=320), nullable=False),
        sa.Column("verification_state", sa.String(length=16), server_default="UNVERIFIED", nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_contact_methods_contact_id_contacts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_contact_methods_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_methods")),
        sa.UniqueConstraint("tenant_id", "kind", "normalized_value", name="uq_contact_methods_tenant_kind_value"),
        sa.CheckConstraint("kind IN ('EMAIL','PHONE','WHATSAPP_ID','INSTAGRAM_HANDLE','MESSENGER_HANDLE')", name="ck_contact_methods_kind"),
        sa.CheckConstraint("verification_state IN ('UNVERIFIED','VERIFIED','INVALID')", name="ck_contact_methods_verification_state"),
    )
    op.create_index(op.f("ix_contact_methods_contact_id"), "contact_methods", ["contact_id"], unique=False)
    op.create_index(op.f("ix_contact_methods_tenant_id"), "contact_methods", ["tenant_id"], unique=False)

    op.create_table(
        "opportunities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("lead_id", sa.Uuid(), nullable=True),
        sa.Column("stage", sa.String(length=24), server_default="NEW", nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("budget_min", sa.BigInteger(), nullable=True),
        sa.Column("budget_max", sa.BigInteger(), nullable=True),
        sa.Column("preferred_configuration", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("loss_reason", sa.String(length=500), nullable=True),
        sa.Column("won_booking_id", sa.Uuid(), nullable=True),
        sa.Column("value_paise", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_opportunities_contact_id_contacts"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_opportunities_project_id_projects"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], name=op.f("fk_opportunities_lead_id_leads"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name=op.f("fk_opportunities_owner_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["won_booking_id"], ["sale_bookings.id"], name=op.f("fk_opportunities_won_booking_id_sale_bookings"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_opportunities_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_opportunities")),
        sa.CheckConstraint("stage IN ('NEW','CONTACTED','QUALIFIED','VISIT_SCHEDULED','VISITED','NEGOTIATING','BOOKED','WON','LOST','LOST_DORMANT')", name="ck_opportunities_stage"),
        sa.CheckConstraint("budget_min IS NULL OR budget_min >= 0", name="ck_opportunities_budget_min"),
        sa.CheckConstraint("budget_max IS NULL OR budget_max >= 0", name="ck_opportunities_budget_max"),
        sa.CheckConstraint("budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max", name="ck_opportunities_budget_ordered"),
    )
    op.create_index(op.f("ix_opportunities_contact_id"), "opportunities", ["contact_id"], unique=False)
    op.create_index(op.f("ix_opportunities_project_id"), "opportunities", ["project_id"], unique=False)
    op.create_index(op.f("ix_opportunities_lead_id"), "opportunities", ["lead_id"], unique=False)
    op.create_index(op.f("ix_opportunities_stage"), "opportunities", ["stage"], unique=False)
    op.create_index(op.f("ix_opportunities_owner_user_id"), "opportunities", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_opportunities_tenant_id"), "opportunities", ["tenant_id"], unique=False)
    op.create_index("ix_opportunities_tenant_contact", "opportunities", ["tenant_id", "contact_id"], unique=False)
    op.create_index("ix_opportunities_tenant_project", "opportunities", ["tenant_id", "project_id"], unique=False)
    op.create_index("ix_opportunities_tenant_owner", "opportunities", ["tenant_id", "owner_user_id"], unique=False)
    op.create_index(
        "uq_opportunities_tenant_lead",
        "opportunities",
        ["tenant_id", "lead_id"],
        unique=True,
        postgresql_where=sa.text("lead_id IS NOT NULL"),
        sqlite_where=sa.text("lead_id IS NOT NULL"),
    )

    op.create_table(
        "contact_merges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("survivor_id", sa.Uuid(), nullable=False),
        sa.Column("merged_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("reverted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["survivor_id"], ["contacts.id"], name=op.f("fk_contact_merges_survivor_id_contacts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["merged_id"], ["contacts.id"], name=op.f("fk_contact_merges_merged_id_contacts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name=op.f("fk_contact_merges_actor_user_id_users"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_contact_merges_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contact_merges")),
    )
    op.create_index(op.f("ix_contact_merges_tenant_id"), "contact_merges", ["tenant_id"], unique=False)
    op.create_index("ix_contact_merges_tenant_survivor", "contact_merges", ["tenant_id", "survivor_id"], unique=False)
    op.create_index("ix_contact_merges_tenant_merged", "contact_merges", ["tenant_id", "merged_id"], unique=False)


def downgrade() -> None:
    """Drop customer graph tables, including auto-emitted composite indexes."""
    op.drop_index("ix_contact_merges_tenant_merged", table_name="contact_merges")
    op.drop_index("ix_contact_merges_tenant_survivor", table_name="contact_merges")
    op.drop_index(op.f("ix_contact_merges_tenant_id"), table_name="contact_merges")
    op.drop_index("ix_contact_merges_tenant_id_id", table_name="contact_merges")
    op.drop_table("contact_merges")

    op.drop_index("uq_opportunities_tenant_lead", table_name="opportunities")
    op.drop_index("ix_opportunities_tenant_owner", table_name="opportunities")
    op.drop_index("ix_opportunities_tenant_project", table_name="opportunities")
    op.drop_index("ix_opportunities_tenant_contact", table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_tenant_id"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_owner_user_id"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_stage"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_lead_id"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_project_id"), table_name="opportunities")
    op.drop_index(op.f("ix_opportunities_contact_id"), table_name="opportunities")
    op.drop_index("ix_opportunities_tenant_id_id", table_name="opportunities")
    op.drop_table("opportunities")

    op.drop_index(op.f("ix_contact_methods_tenant_id"), table_name="contact_methods")
    op.drop_index(op.f("ix_contact_methods_contact_id"), table_name="contact_methods")
    op.drop_index("ix_contact_methods_tenant_id_id", table_name="contact_methods")
    op.drop_table("contact_methods")

    op.drop_index("ix_contacts_tenant_status", table_name="contacts")
    op.drop_index(op.f("ix_contacts_tenant_id"), table_name="contacts")
    op.drop_index(op.f("ix_contacts_status"), table_name="contacts")
    op.drop_index("ix_contacts_tenant_id_id", table_name="contacts")
    op.drop_table("contacts")
