"""Canonical property units, append-only status history, and exclusive holds."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.tenancy import TenantOwned


class UnitStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    AVAILABLE = "AVAILABLE"
    ON_HOLD = "ON_HOLD"
    RESERVED = "RESERVED"
    BOOKED = "BOOKED"
    SOLD = "SOLD"
    BLOCKED = "BLOCKED"
    UNDER_DISPUTE = "UNDER_DISPUTE"
    CANCELLED = "CANCELLED"


class HoldState(StrEnum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CONVERTED = "CONVERTED"
    RELEASED = "RELEASED"
    CANCELLED = "CANCELLED"


class DiscountStatus(StrEnum):
    """Approval-tracked discount flag on a canonical unit."""

    NONE = "NONE"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class UnitEventSource(StrEnum):
    MANUAL = "MANUAL"
    HOLD = "HOLD"
    BOOKING = "BOOKING"
    CANCELLATION = "CANCELLATION"


class HoldReleaseSource(StrEnum):
    EXPIRY = "EXPIRY"
    MANUAL = "MANUAL"
    CONVERTED = "CONVERTED"
    CANCELLED = "CANCELLED"


def utcnow() -> datetime:
    return datetime.now(UTC)


def _enum_values(values: type[StrEnum]) -> str:
    return ", ".join(f"'{value.value}'" for value in values)


class PropertyUnit(TenantOwned, Base):
    """Canonical inventory row; sale_bookings.unit_number remains legacy text."""

    __tablename__ = "property_units"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_enum_values(UnitStatus)})", name="unit_status_valid"
        ),
        CheckConstraint(
            f"discount_status IN ({_enum_values(DiscountStatus)})",
            name="unit_discount_status_valid",
        ),
        CheckConstraint(
            "approved_discount_paise IS NULL OR approved_discount_paise > 0",
            name="unit_approved_discount_positive",
        ),
        CheckConstraint(
            "carpet_area_sqft IS NULL OR carpet_area_sqft > 0",
            name="carpet_area_positive",
        ),
        CheckConstraint(
            "built_up_area_sqft IS NULL OR built_up_area_sqft > 0",
            name="built_up_area_positive",
        ),
        UniqueConstraint(
            "tenant_id", "project_id", "internal_code",
            name="uq_property_units_tenant_project_code",
        ),
        Index("ix_property_units_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    internal_code: Mapped[str] = mapped_column(String(64), nullable=False)
    configuration: Mapped[str | None] = mapped_column(String(100), nullable=True)
    floor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    position: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tower: Mapped[str | None] = mapped_column(String(64), nullable=True)
    carpet_area_sqft: Mapped[int | None] = mapped_column(nullable=True)
    built_up_area_sqft: Mapped[int | None] = mapped_column(nullable=True)
    plot_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    facing: Mapped[str | None] = mapped_column(String(64), nullable=True)
    views: Mapped[str | None] = mapped_column(String(255), nullable=True)
    saleable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=UnitStatus.DRAFT.value,
        server_default=UnitStatus.DRAFT.value,
    )
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Approval-wired discount fields: the amount is written only by an APPROVED
    # DISCOUNT decision (never on REJECT); the flag tracks the request state.
    approved_discount_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    discount_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DiscountStatus.NONE.value,
        server_default=DiscountStatus.NONE.value,
    )
    rera_disclosure_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow,
        server_default=func.now(), onupdate=utcnow,
    )


class UnitStatusEvent(TenantOwned, Base):
    """Append-only evidence of every effective unit status transition."""

    __tablename__ = "unit_status_events"
    __table_args__ = (
        CheckConstraint(
            f"from_status IN ({_enum_values(UnitStatus)})", name="event_from_status_valid"
        ),
        CheckConstraint(
            f"to_status IN ({_enum_values(UnitStatus)})", name="event_to_status_valid"
        ),
        CheckConstraint(
            f"source IN ({_enum_values(UnitEventSource)})", name="event_source_valid"
        ),
        Index("ix_unit_status_events_unit_effective", "unit_id", "effective_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    unit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("property_units.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    from_status: Mapped[str] = mapped_column(String(24), nullable=False)
    to_status: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    event_meta: Mapped[dict] = mapped_column("meta", JSON, nullable=False, default=dict)


class UnitHold(TenantOwned, Base):
    """A time-bound, owner-scoped claim on exactly one canonical unit.

    The partial unique index, not an application-side existence check, is the
    final authority that a unit has at most one ACTIVE hold.
    """

    __tablename__ = "unit_holds"
    __table_args__ = (
        CheckConstraint(
            f"state IN ({_enum_values(HoldState)})", name="hold_state_valid"
        ),
        CheckConstraint(
            "release_source IS NULL OR release_source IN "
            "('EXPIRY','MANUAL','CONVERTED','CANCELLED')",
            name="hold_release_source_valid",
        ),
        CheckConstraint(
            "extension_count >= 0 AND extension_count <= 2", name="hold_extension_policy"
        ),
        Index(
            "uq_unit_holds_one_active_per_unit", "tenant_id", "unit_id", unique=True,
            sqlite_where=text("state = 'ACTIVE'"),
            postgresql_where=text("state = 'ACTIVE'"),
        ),
        Index("ix_unit_holds_tenant_expiry", "tenant_id", "state", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    unit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("property_units.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    opportunity_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lead_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default=HoldState.ACTIVE.value,
        server_default=HoldState.ACTIVE.value,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    extension_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    converted_booking_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sale_bookings.id", ondelete="SET NULL"), nullable=True
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    release_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow,
        server_default=func.now(), onupdate=utcnow,
    )
