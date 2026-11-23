"""Unit handover cases, independently verified snags and key register."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.tenancy import TenantOwned


class HandoverStatus(StrEnum):
    CHECKLIST = "CHECKLIST"
    IN_PROGRESS = "IN_PROGRESS"
    SNAG_OPEN = "SNAG_OPEN"
    READY = "READY"
    HANDED_OVER = "HANDED_OVER"


class SnagStatus(StrEnum):
    OPEN = "OPEN"
    FIXED = "FIXED"
    VERIFIED = "VERIFIED"
    CLOSED = "CLOSED"


class SnagSeverity(StrEnum):
    MINOR = "MINOR"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"


def utcnow() -> datetime:
    return datetime.now(UTC)


class HandoverCase(TenantOwned, Base):
    """Possession workflow anchored to a canonical inventory unit."""

    __tablename__ = "handover_cases"
    __table_args__ = (
        CheckConstraint(
            "status IN ('CHECKLIST','IN_PROGRESS','SNAG_OPEN','READY','HANDED_OVER')",
            name="ck_handover_cases_status",
        ),
        Index("ix_handover_cases_tenant_unit", "tenant_id", "unit_id", unique=True),
        Index("ix_handover_cases_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    unit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("property_units.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    booking_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sale_bookings.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=HandoverStatus.CHECKLIST.value,
        server_default=HandoverStatus.CHECKLIST.value,
    )
    readiness: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    registration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    registration_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    possession_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    override_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handed_over_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handed_over_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(), onupdate=utcnow
    )


class SnagItem(TenantOwned, Base):
    """A unit defect; FIXED and VERIFIED are deliberately separate actions."""

    __tablename__ = "handover_snags"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN','FIXED','VERIFIED','CLOSED')", name="ck_handover_snags_status"
        ),
        CheckConstraint(
            "severity IN ('MINOR','MAJOR','CRITICAL')", name="ck_handover_snags_severity"
        ),
        Index("ix_handover_snags_tenant_case_status", "tenant_id", "case_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("handover_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default=SnagSeverity.MINOR.value, server_default=SnagSeverity.MINOR.value)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SnagStatus.OPEN.value, server_default=SnagStatus.OPEN.value
    )
    photo_evidence_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    photo_content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    photo_content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assigned_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    fixed_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    fixed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(), onupdate=utcnow
    )


class KeyHandover(TenantOwned, Base):
    """Recorded keys/access cards issued to a recipient for a handover case."""

    __tablename__ = "handover_keys"
    __table_args__ = (
        CheckConstraint("keys_count >= 0", name="ck_handover_keys_non_negative"),
        CheckConstraint("cards_count >= 0", name="ck_handover_cards_non_negative"),
        Index("ix_handover_keys_tenant_case", "tenant_id", "case_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("handover_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    keys_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    cards_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    handed_to_name: Mapped[str] = mapped_column(String(255), nullable=False)
    handed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    collected_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(), onupdate=utcnow
    )
