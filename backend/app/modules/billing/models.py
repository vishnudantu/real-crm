"""Billing models: subscriptions, invoices, and processed webhook events."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.tenancy import TenantOwned


class SubscriptionStatus(StrEnum):
    CREATED = "created"
    AUTHORIZING = "authorizing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    HALTED = "halted"
    CANCELLED = "cancelled"


def utcnow() -> datetime:
    return datetime.now(UTC)


class Subscription(TenantOwned, Base):
    """A tenant's Razorpay subscription mapped to a plan and lifecycle state."""

    __tablename__ = "subscriptions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SubscriptionStatus.CREATED.value, index=True
    )
    razorpay_plan_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    razorpay_subscription_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, unique=True
    )
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )


class Invoice(TenantOwned, Base):
    """A billing invoice derived from Razorpay payment/subscription events."""

    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "razorpay_invoice_id", name="uq_invoices_tenant_razorpay"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    subscription_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    razorpay_invoice_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class BillingWebhookEvent(Base):
    """Global provider event ledger providing replay protection via unique event id."""

    __tablename__ = "billing_webhook_events"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
