"""Deal-desk pricing artifacts: cost sheets, discount matrices, quotes.

Three tenant-owned tables:

- deal_desk_cost_sheets: one costing per project (generic) or per unit
  (unit-specific). unit_id NULL means the project-level sheet. The breakdown
  JSON is the system of record; land/construction/amenities/margin paise
  columns are derived (kept in sync by the service) so the total is one
  indexed SUM, never a JSON walk.
- deal_desk_discount_matrix_bands: the tenant's editable percent-band policy.
  Bands with a maximum cover (0, max%]; a band with a NULL maximum is the
  open-ended ceiling band and must be blocked. band_number is unique per
  tenant. Defaults are seeded per tenant by the migration and by
  get_or_create_matrix.
- deal_desk_quotes: a priced proposal snapshot. Quoting validates against the
  matrix but never flags the unit; raising a discount from a quote is the only
  path that opens a DEAL_DISCOUNT approval and moves the unit to PENDING.

Money is integer paise everywhere. Percent thresholds are Decimal(5,2) so a
2.00 band never drifts through float rounding.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.tenancy import TenantOwned


def utcnow() -> datetime:
    return datetime.now(UTC)


class QuoteStatus(StrEnum):
    QUOTED = "QUOTED"
    REQUESTED = "REQUESTED"


# The tenant's discount policy, as constants a reviewer can check against the
# deal-desk SOP. band1 <=2% needs one admin approval; band2 <=5% needs admin
# approval plus a mandatory reason; anything above 5% (the ceiling band) is
# blocked at creation with a policy message.
DEFAULT_MATRIX_BANDS: tuple[dict, ...] = (
    {
        "band_number": 1,
        "max_discount_percent": Decimal("2.00"),
        "reason_required": False,
        "blocked": False,
        "description": "Up to 2% off — one administrator approval.",
    },
    {
        "band_number": 2,
        "max_discount_percent": Decimal("5.00"),
        "reason_required": True,
        "blocked": False,
        "description": "Up to 5% off — administrator approval with a mandatory reason.",
    },
    {
        "band_number": 3,
        "max_discount_percent": None,
        "reason_required": True,
        "blocked": True,
        "description": "Above 5% off — blocked by deal-desk policy.",
    },
)


def default_matrix_rows() -> list[dict]:
    """Fresh mutable copies of the seeded defaults (never hand out the tuple)."""

    return [dict(row) for row in DEFAULT_MATRIX_BANDS]


class CostSheet(TenantOwned, Base):
    """Cost-build-up sheet attached to a project (generic) or one unit."""

    __tablename__ = "deal_desk_cost_sheets"
    __table_args__ = (
        CheckConstraint(
            "land_paise >= 0 AND construction_paise >= 0 "
            "AND amenities_paise >= 0 AND margin_paise >= 0",
            name="cost_components_non_negative",
        ),
        CheckConstraint("total_paise >= 0", name="cost_total_non_negative"),
        Index(
            "uq_deal_desk_cost_sheets_project_sheet",
            "tenant_id", "project_id", unique=True,
            sqlite_where=text("unit_id IS NULL"),
            postgresql_where=text("unit_id IS NULL"),
        ),
        Index(
            "uq_deal_desk_cost_sheets_unit_sheet", "unit_id", unique=True,
            sqlite_where=text("unit_id IS NOT NULL"),
            postgresql_where=text("unit_id IS NOT NULL"),
        ),
        Index("ix_deal_desk_cost_sheets_tenant_project", "tenant_id", "project_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    unit_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("property_units.id", ondelete="CASCADE"),
        nullable=True,
    )
    # Derived from cost_breakdown_json on every write; the JSON stays the
    # system of record so future components never need a column.
    land_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    construction_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    amenities_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    margin_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cost_breakdown_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow,
        server_default=func.now(), onupdate=utcnow,
    )


class DiscountMatrixBand(TenantOwned, Base):
    """One editable percent band of the tenant's discount approval matrix."""

    __tablename__ = "deal_desk_discount_matrix_bands"
    __table_args__ = (
        CheckConstraint("band_number >= 1", name="matrix_band_number_positive"),
        CheckConstraint(
            "max_discount_percent IS NULL OR "
            "(max_discount_percent > 0 AND max_discount_percent <= 100)",
            name="matrix_band_percent_range",
        ),
        CheckConstraint(
            "NOT (blocked AND max_discount_percent IS NOT NULL)",
            name="matrix_blocked_band_is_ceiling",
        ),
        Index(
            "uq_deal_desk_matrix_tenant_band_number",
            "tenant_id", "band_number", unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    band_number: Mapped[int] = mapped_column(nullable=False)
    # NULL maximum = the open-ended ceiling band (always blocked).
    max_discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    reason_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    blocked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow,
        server_default=func.now(), onupdate=utcnow,
    )


class DiscountQuote(TenantOwned, Base):
    """A priced proposal snapshot: gross, discount and net in integer paise."""

    __tablename__ = "deal_desk_quotes"
    __table_args__ = (
        CheckConstraint("gross_price_paise > 0", name="quote_gross_positive"),
        CheckConstraint("discount_paise >= 0", name="quote_discount_non_negative"),
        CheckConstraint("net_price_paise > 0", name="quote_net_positive"),
        CheckConstraint(
            "status IN ('QUOTED','REQUESTED')", name="quote_status_valid"
        ),
        Index("ix_deal_desk_quotes_tenant_unit", "tenant_id", "unit_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    unit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("property_units.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    cost_sheet_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("deal_desk_cost_sheets.id", ondelete="SET NULL"),
        nullable=True,
    )
    gross_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    net_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    band_number: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=QuoteStatus.QUOTED.value,
        server_default=QuoteStatus.QUOTED.value,
    )
    customer_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow,
        server_default=func.now(), onupdate=utcnow,
    )
