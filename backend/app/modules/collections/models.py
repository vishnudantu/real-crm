"""Collections command centre models.

Two small tenant-owned tables:

- ``collection_reminders``: dedupe ledger for the reminder sequencer. One row
  per (tenant, installment, offset_key) so a given offset for an installment
  is queued at most once even when the daily job re-runs.
- ``installment_promises``: buyer promises to pay. Record-only: these rows
  never alter installment amounts, receipts, or balances.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
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


def utcnow() -> datetime:
    return datetime.now(UTC)


class CollectionReminder(TenantOwned, Base):
    """Dedupe record: one reminder per (tenant, installment, offset_key).

    The unique constraint is the concurrency-safe guard against duplicate
    queueing when the scheduler runs more than once per day or on multiple
    workers. The linked ``message_deliveries`` row carries the actual outbox
    payload and its own idempotency key.
    """

    __tablename__ = "collection_reminders"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "installment_id", "offset_key",
            name="uq_collection_reminders_tenant_installment_offset",
        ),
        Index(
            "ix_collection_reminders_tenant_scheduled",
            "tenant_id", "scheduled_for",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    installment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("installments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Offset in days relative to the installment due date; string keeps the
    # unique key stable for negative values ("-7", "0", "+14" normalized).
    offset_key: Mapped[str] = mapped_column(String(8), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
    )


class InstallmentPromise(TenantOwned, Base):
    """A buyer's promise to pay an installment by a date. Never moves money."""

    __tablename__ = "installment_promises"
    __table_args__ = (
        CheckConstraint("amount_paise >= 0", name="ck_installment_promises_amount_non_negative"),
        Index(
            "ix_installment_promises_tenant_installment",
            "tenant_id", "installment_id",
        ),
        Index(
            "ix_installment_promises_tenant_promised_on",
            "tenant_id", "promised_on",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    installment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("installments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    promised_on: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
    )
