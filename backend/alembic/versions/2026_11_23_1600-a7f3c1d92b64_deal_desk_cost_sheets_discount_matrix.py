"""deal desk: cost sheets, tenant discount matrix bands, quotes

Revision ID: a7f3c1d92b64
Revises: e2b7c4a9d1f6
Create Date: 2026-11-23 16:00:00

Additive, idempotent, and batch-safe on SQLite. The ix_<table>_tenant_id_id
composite indexes are intentionally NOT created here: the after_parent_attach
listener in app.db.tenancy auto-emits them from ORM metadata, and creating
them explicitly would fail with "index already exists" when the ORM builds
the same schema (tests) and diverge from it otherwise.

Existing tenants receive the default 2% / 5% / blocked-above matrix on upgrade
(created_at supplied explicitly: the DEFAULT now() server default breaks on
SQLite). Tenants created later are seeded lazily by the deal-desk service.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "a7f3c1d92b64"
down_revision: Union[str, None] = "e2b7c4a9d1f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _index_names(inspector, table: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table)}


def _table_names(inspector) -> set[str]:
    return set(inspector.get_table_names())


DEFAULT_MATRIX = (
    # (band_number, max_discount_percent, reason_required, blocked, description)
    (1, Decimal("2.00"), False, False, "Up to 2% off — one administrator approval."),
    (2, Decimal("5.00"), True, False, "Up to 5% off — administrator approval with a mandatory reason."),
    (3, None, True, True, "Above 5% off — blocked by deal-desk policy."),
)


def _seed_default_matrices(bind) -> None:
    """Insert the three default bands for every tenant that has none.

    Typed Core columns round-trip SQLAlchemy's Uuid storage format on both
    SQLite and PostgreSQL; created_at/updated_at are supplied explicitly
    because the columns' server_default now() is not portable to SQLite
    inserts.
    """
    tenants = sa.table("tenants", sa.column("id", sa.Uuid()))
    bands = sa.table(
        "deal_desk_discount_matrix_bands",
        sa.column("id", sa.Uuid()),
        sa.column("tenant_id", sa.Uuid()),
        sa.column("band_number", sa.Integer()),
        sa.column("max_discount_percent", sa.Numeric(5, 2)),
        sa.column("reason_required", sa.Boolean()),
        sa.column("blocked", sa.Boolean()),
        sa.column("description", sa.String(255)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    tenant_ids = bind.execute(sa.select(tenants.c.id)).scalars().all()
    if not tenant_ids:
        return
    existing = set(
        bind.execute(sa.select(bands.c.tenant_id).distinct()).scalars().all()
    )
    now = datetime.now(UTC)
    rows = []
    for tenant_id in tenant_ids:
        if tenant_id in existing:
            continue
        for band_number, maximum, reason_required, blocked, description in DEFAULT_MATRIX:
            rows.append(
                {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "band_number": band_number,
                    "max_discount_percent": maximum,
                    "reason_required": reason_required,
                    "blocked": blocked,
                    "description": description,
                    "created_at": now,
                    "updated_at": now,
                }
            )
    if rows:
        op.bulk_insert(bands, rows)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = _table_names(inspector)

    if "deal_desk_cost_sheets" not in tables:
        op.create_table(
            "deal_desk_cost_sheets",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("unit_id", sa.Uuid(), nullable=True),
            sa.Column("land_paise", sa.BigInteger(), server_default="0", nullable=False),
            sa.Column("construction_paise", sa.BigInteger(), server_default="0", nullable=False),
            sa.Column("amenities_paise", sa.BigInteger(), server_default="0", nullable=False),
            sa.Column("margin_paise", sa.BigInteger(), server_default="0", nullable=False),
            sa.Column("total_paise", sa.BigInteger(), server_default="0", nullable=False),
            sa.Column("cost_breakdown_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
            sa.Column("note", sa.String(length=500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.CheckConstraint(
                "land_paise >= 0 AND construction_paise >= 0 "
                "AND amenities_paise >= 0 AND margin_paise >= 0",
                name=op.f("ck_deal_desk_cost_sheets_cost_components_non_negative"),
            ),
            sa.CheckConstraint(
                "total_paise >= 0",
                name=op.f("ck_deal_desk_cost_sheets_cost_total_non_negative"),
            ),
            sa.ForeignKeyConstraint(
                ["project_id"], ["projects.id"],
                name=op.f("fk_deal_desk_cost_sheets_project_id_projects"), ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name=op.f("fk_deal_desk_cost_sheets_tenant_id_tenants"), ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["unit_id"], ["property_units.id"],
                name=op.f("fk_deal_desk_cost_sheets_unit_id_property_units"), ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_deal_desk_cost_sheets")),
        )
        op.create_index(
            op.f("ix_deal_desk_cost_sheets_tenant_id"),
            "deal_desk_cost_sheets", ["tenant_id"], unique=False,
        )
        op.create_index(
            "ix_deal_desk_cost_sheets_tenant_project",
            "deal_desk_cost_sheets", ["tenant_id", "project_id"], unique=False,
        )
    inspector = sa.inspect(op.get_bind())
    if "deal_desk_cost_sheets" in inspector.get_table_names():
        existing = _index_names(inspector, "deal_desk_cost_sheets")
        for name, columns, unique, where in (
            (
                "uq_deal_desk_cost_sheets_project_sheet",
                ["tenant_id", "project_id"], True, "unit_id IS NULL",
            ),
            (
                "uq_deal_desk_cost_sheets_unit_sheet",
                ["unit_id"], True, "unit_id IS NOT NULL",
            ),
        ):
            if name not in existing:
                op.create_index(
                    name, "deal_desk_cost_sheets", columns, unique=unique,
                    sqlite_where=sa.text(where), postgresql_where=sa.text(where),
                )

    if "deal_desk_discount_matrix_bands" not in tables:
        op.create_table(
            "deal_desk_discount_matrix_bands",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("band_number", sa.Integer(), nullable=False),
            sa.Column("max_discount_percent", sa.Numeric(5, 2), nullable=True),
            sa.Column("reason_required", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("blocked", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.CheckConstraint(
                "band_number >= 1",
                name=op.f("ck_deal_desk_discount_matrix_bands_matrix_band_number_positive"),
            ),
            sa.CheckConstraint(
                "max_discount_percent IS NULL OR "
                "(max_discount_percent > 0 AND max_discount_percent <= 100)",
                name=op.f("ck_deal_desk_discount_matrix_bands_matrix_band_percent_range"),
            ),
            sa.CheckConstraint(
                "NOT (blocked AND max_discount_percent IS NOT NULL)",
                name=op.f("ck_deal_desk_discount_matrix_bands_matrix_blocked_band_is_ceiling"),
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name=op.f("fk_deal_desk_discount_matrix_bands_tenant_id_tenants"),
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_deal_desk_discount_matrix_bands")),
        )
        op.create_index(
            op.f("ix_deal_desk_discount_matrix_bands_tenant_id"),
            "deal_desk_discount_matrix_bands", ["tenant_id"], unique=False,
        )
        op.create_index(
            "uq_deal_desk_matrix_tenant_band_number",
            "deal_desk_discount_matrix_bands", ["tenant_id", "band_number"], unique=True,
        )
    _seed_default_matrices(op.get_bind())

    if "deal_desk_quotes" not in tables:
        op.create_table(
            "deal_desk_quotes",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("unit_id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("cost_sheet_id", sa.Uuid(), nullable=True),
            sa.Column("gross_price_paise", sa.BigInteger(), nullable=False),
            sa.Column("discount_paise", sa.BigInteger(), nullable=False),
            sa.Column("discount_percent", sa.Numeric(7, 2), nullable=False),
            sa.Column("net_price_paise", sa.BigInteger(), nullable=False),
            sa.Column("band_number", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=16), server_default="QUOTED", nullable=False),
            sa.Column("customer_ref", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.CheckConstraint(
                "gross_price_paise > 0",
                name=op.f("ck_deal_desk_quotes_quote_gross_positive"),
            ),
            sa.CheckConstraint(
                "discount_paise >= 0",
                name=op.f("ck_deal_desk_quotes_quote_discount_non_negative"),
            ),
            sa.CheckConstraint(
                "net_price_paise > 0",
                name=op.f("ck_deal_desk_quotes_quote_net_positive"),
            ),
            sa.CheckConstraint(
                "status IN ('QUOTED','REQUESTED')",
                name=op.f("ck_deal_desk_quotes_quote_status_valid"),
            ),
            sa.ForeignKeyConstraint(
                ["cost_sheet_id"], ["deal_desk_cost_sheets.id"],
                name=op.f("fk_deal_desk_quotes_cost_sheet_id_deal_desk_cost_sheets"),
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(
                ["project_id"], ["projects.id"],
                name=op.f("fk_deal_desk_quotes_project_id_projects"), ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id"], ["tenants.id"],
                name=op.f("fk_deal_desk_quotes_tenant_id_tenants"), ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["unit_id"], ["property_units.id"],
                name=op.f("fk_deal_desk_quotes_unit_id_property_units"), ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_deal_desk_quotes")),
        )
        op.create_index(
            op.f("ix_deal_desk_quotes_tenant_id"),
            "deal_desk_quotes", ["tenant_id"], unique=False,
        )
        op.create_index(
            "ix_deal_desk_quotes_tenant_unit",
            "deal_desk_quotes", ["tenant_id", "unit_id"], unique=False,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = _table_names(inspector)
    for table, indexes in (
        (
            "deal_desk_quotes",
            (
                "ix_deal_desk_quotes_tenant_unit",
                op.f("ix_deal_desk_quotes_tenant_id"),
            ),
        ),
        (
            "deal_desk_discount_matrix_bands",
            (
                "uq_deal_desk_matrix_tenant_band_number",
                op.f("ix_deal_desk_discount_matrix_bands_tenant_id"),
            ),
        ),
        (
            "deal_desk_cost_sheets",
            (
                "uq_deal_desk_cost_sheets_unit_sheet",
                "uq_deal_desk_cost_sheets_project_sheet",
                "ix_deal_desk_cost_sheets_tenant_project",
                op.f("ix_deal_desk_cost_sheets_tenant_id"),
            ),
        ),
    ):
        if table not in tables:
            continue
        for name in indexes:
            if name in _index_names(inspector, table):
                op.drop_index(name, table_name=table)
        op.drop_table(table)
