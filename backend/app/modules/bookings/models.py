"""SQLAlchemy models for visit slots and site visit bookings."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.tenancy import TenantOwned
from app.modules.customers.models import Contact
from app.modules.leads.models import Lead
from app.modules.projects.models import Project
from app.modules.users.models import User


class BookingStatus(StrEnum):
    """Lifecycle states for a site visit booking."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"


class CarRequestStatus(StrEnum):
    """Approval-tracked chauffeur car request flag on a booking."""

    NONE = "NONE"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class EvidenceStatus(StrEnum):
    """Staff-uploaded visit evidence verification lifecycle."""

    SUBMITTED = "SUBMITTED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


ACTIVE_BOOKING_STATUSES: tuple[str, ...] = (
    BookingStatus.PENDING.value,
    BookingStatus.CONFIRMED.value,
)


def utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(UTC)


def _quoted_values(values: type[StrEnum]) -> str:
    return ", ".join(f"'{value.value}'" for value in values)


class VisitSlot(TenantOwned, Base):
    """An available time window for prospective buyers to visit a project."""

    __tablename__ = "visit_slots"
    __table_args__ = (
        CheckConstraint(
            "start_time < end_time",
            name="ck_visit_slots_start_before_end",
        ),
        CheckConstraint(
            "capacity >= 1",
            name="ck_visit_slots_capacity_positive",
        ),
        UniqueConstraint(
            "project_id",
            "start_time",
            "end_time",
            name="uq_visit_slots_project_time_range",
        ),
        Index("ix_visit_slots_project_id_start_time", "project_id", "start_time"),
        Index("ix_visit_slots_is_active_start_time", "is_active", "start_time"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    capacity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
    )

    project: Mapped[Project] = relationship()
    bookings: Mapped[list[Booking]] = relationship(
        back_populates="slot",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Booking(TenantOwned, Base):
    """A site visit reservation linked to a visit slot, lead, and project."""

    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_quoted_values(BookingStatus)})",
            name="ck_bookings_status",
        ),
        CheckConstraint(
            f"car_request_status IN ({_quoted_values(CarRequestStatus)})",
            name="ck_bookings_car_request_status",
        ),
        Index("ix_bookings_slot_id_status", "slot_id", "status"),
        Index("ix_bookings_buyer_id_created_at", "buyer_id", "created_at"),
        Index("ix_bookings_project_id_created_at", "project_id", "created_at"),
        Index("ix_bookings_lead_id_created_at", "lead_id", "created_at"),
        Index("ix_bookings_executive_id_created_at", "executive_id", "created_at"),
        Index(
            "uq_bookings_lead_slot_active",
            "lead_id",
            "slot_id",
            unique=True,
            postgresql_where=text("status NOT IN ('CANCELLED')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    slot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("visit_slots.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("leads.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Native link to the canonical customer identity (PF-008). Additive:
    # lead_id stays the intake system-of-record; the UI no longer needs to
    # mirror new customers into contacts to attribute a visit.
    contact_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    buyer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    executive_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=BookingStatus.CONFIRMED.value,
        server_default=BookingStatus.CONFIRMED.value,
        index=True,
    )
    car_request_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CarRequestStatus.NONE.value,
        server_default=CarRequestStatus.NONE.value,
    )
    cancellation_reason: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
    )

    slot: Mapped[VisitSlot] = relationship(back_populates="bookings")
    lead: Mapped[Lead] = relationship()
    contact: Mapped[Contact | None] = relationship()
    project: Mapped[Project] = relationship()
    buyer: Mapped[User] = relationship(foreign_keys=[buyer_id])
    executive: Mapped[User | None] = relationship(foreign_keys=[executive_id])
    cancelled_by: Mapped[User | None] = relationship(foreign_keys=[cancelled_by_id])


class VisitEvidence(TenantOwned, Base):
    """Staff-uploaded proof that a site visit happened (photo/document + notes).

    Metadata is stored here; binary content lives in local disk storage rooted at
    VISIT_EVIDENCE_STORAGE_DIR with a per-tenant subfolder. ``content_sha256`` and
    the relative ``storage_path`` give an integrity check without exposing
    absolute paths through the API. Verification is a separate staff action.
    """

    __tablename__ = "visit_evidence"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_quoted_values(EvidenceStatus)})",
            name="ck_visit_evidence_status",
        ),
        CheckConstraint(
            "length(content_sha256) = 64", name="ck_visit_evidence_sha256"
        ),
        CheckConstraint("size_bytes >= 0", name="ck_visit_evidence_size_non_negative"),
        Index("ix_visit_evidence_booking", "booking_id"),
        Index("ix_visit_evidence_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    booking_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=EvidenceStatus.SUBMITTED.value,
        server_default=EvidenceStatus.SUBMITTED.value,
    )
    uploaded_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )

    booking: Mapped[Booking] = relationship(foreign_keys=[booking_id])

