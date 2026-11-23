"""Connect dialer models: dispositions, DNC suppression, scheduled callbacks."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.tenancy import TenantOwned


class Disposition(StrEnum):
    INTERESTED = "INTERESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    VISIT_CONFIRMED = "VISIT_CONFIRMED"
    CALL_BACK = "CALL_BACK"
    WRONG_NUMBER = "WRONG_NUMBER"
    PAYMENT_DISCUSSION = "PAYMENT_DISCUSSION"
    ESCALATION = "ESCALATION"
    NO_ANSWER = "NO_ANSWER"


class CallbackStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


def utcnow() -> datetime:
    return datetime.now(UTC)


def _quoted(values: type[StrEnum]) -> str:
    return ", ".join(f"'{v.value}'" for v in values)


class CallDisposition(TenantOwned, Base):
    """The outcome an executive records after a call ends (one per call)."""

    __tablename__ = "call_dispositions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "call_id", name="uq_call_dispositions_call"),
        CheckConstraint(f"disposition IN ({_quoted(Disposition)})", name="ck_call_dispositions_value"),
        Index("ix_call_dispositions_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    call_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("call_records.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    disposition: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )


class DoNotCallEntry(TenantOwned, Base):
    """A phone number this tenant must not dial, with an audit reason."""

    __tablename__ = "do_not_call_entries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "phone_number", name="uq_do_not_call_tenant_phone"),
        Index("ix_do_not_call_tenant_phone", "tenant_id", "phone_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    added_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class ScheduledCallback(TenantOwned, Base):
    """A callback promised to a customer, with an assignee and a reminder time."""

    __tablename__ = "scheduled_callbacks"
    __table_args__ = (
        CheckConstraint(f"status IN ({_quoted(CallbackStatus)})", name="ck_scheduled_callbacks_status"),
        Index("ix_scheduled_callbacks_tenant_status_time", "tenant_id", "status", "scheduled_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    call_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("call_records.id", ondelete="SET NULL"), nullable=True
    )
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_to_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CallbackStatus.SCHEDULED.value,
        server_default=CallbackStatus.SCHEDULED.value,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )
