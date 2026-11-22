"""Post-sales data model: from site visit to registered sale with a payment ledger."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    Numeric,
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


class SaleStatus(StrEnum):
    BOOKED = "BOOKED"
    AGREEMENT_PENDING = "AGREEMENT_PENDING"
    AGREEMENT_SIGNED = "AGREEMENT_SIGNED"
    PAYMENTS_IN_PROGRESS = "PAYMENTS_IN_PROGRESS"
    POSSESSION_READY = "POSSESSION_READY"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class PaymentPlanType(StrEnum):
    CONSTRUCTION_LINKED = "CONSTRUCTION_LINKED"
    TIME_LINKED = "TIME_LINKED"
    HYBRID = "HYBRID"


class InstallmentStatus(StrEnum):
    PENDING = "PENDING"
    DUE = "DUE"
    PART_PAID = "PART_PAID"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    WAIVED = "WAIVED"


class ReceiptChannel(StrEnum):
    UPI = "UPI"
    CHEQUE = "CHEQUE"
    NEFT = "NEFT"
    CASH = "CASH"
    CARD = "CARD"
    LOAN_DISBURSAL = "LOAN_DISBURSAL"


class CommissionStatus(StrEnum):
    PENDING = "PENDING"
    PAYABLE = "PAYABLE"
    PAID = "PAID"
    REVERSED = "REVERSED"


def utcnow() -> datetime:
    return datetime.now(UTC)


class SaleBooking(TenantOwned, Base):
    """A converted buyer's property booking: unit, consideration and timeline."""

    __tablename__ = "sale_bookings"
    __table_args__ = (
        CheckConstraint("consideration_paise >= 0", name="consideration_non_negative"),
        Index("ix_sale_bookings_tenant_status", "tenant_id", "status"),
        Index("ix_sale_bookings_tenant_lead", "tenant_id", "lead_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("leads.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    customer_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    unit_number: Mapped[str] = mapped_column(String(64), nullable=False)
    # Canonical unit pointer (PF-010). Nullable so legacy free-text rows stay valid.
    unit_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("property_units.id", ondelete="RESTRICT"),
        nullable=True, index=True,
    )
    configuration: Mapped[str | None] = mapped_column(String(100), nullable=True)
    carpet_area_sqft: Mapped[int | None] = mapped_column(nullable=True)
    consideration_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=SaleStatus.BOOKED.value,
        server_default=SaleStatus.BOOKED.value,
    )
    booked_on: Mapped[date] = mapped_column(Date, nullable=False, default=lambda: date.today())
    agreement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_possession: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )

    plans: Mapped[list["PaymentPlan"]] = relationship(back_populates="booking")


class PaymentPlan(TenantOwned, Base):
    """Milestone schedule for a sale booking."""

    __tablename__ = "payment_plans"
    __table_args__ = (
        CheckConstraint("plan_type IN ('CONSTRUCTION_LINKED','TIME_LINKED','HYBRID')", name="plan_type_valid"),
        Index("ix_payment_plans_booking", "sale_booking_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    sale_booking_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sale_bookings.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_type: Mapped[str] = mapped_column(String(24), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    booking: Mapped[SaleBooking] = relationship(back_populates="plans")
    installments: Mapped[list["Installment"]] = relationship(back_populates="plan")


class Installment(TenantOwned, Base):
    """A scheduled demand on a payment plan."""

    __tablename__ = "installments"
    __table_args__ = (
        CheckConstraint("amount_paise >= 0", name="installment_amount_non_negative"),
        UniqueConstraint("plan_id", "sequence_no", name="uq_installments_plan_sequence"),
        Index("ix_installments_tenant_status_due", "tenant_id", "status", "due_on"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("payment_plans.id", ondelete="CASCADE"), nullable=False
    )
    sequence_no: Mapped[int] = mapped_column(nullable=False)
    milestone: Mapped[str] = mapped_column(String(160), nullable=False)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    due_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=InstallmentStatus.PENDING.value,
        server_default=InstallmentStatus.PENDING.value,
    )
    demand_letter_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )

    plan: Mapped[PaymentPlan] = relationship(back_populates="installments")


class Receipt(TenantOwned, Base):
    """Append-only ledger entry for a payment received against an installment."""

    __tablename__ = "receipts"
    __table_args__ = (
        CheckConstraint("amount_paise > 0", name="receipt_amount_positive"),
        UniqueConstraint("tenant_id", "receipt_number", name="uq_receipts_tenant_number"),
        Index("ix_receipts_tenant_paid_at", "tenant_id", "paid_at"),
        Index(
            "uq_receipts_tenant_idempotency_key",
            "tenant_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
            sqlite_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    installment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("installments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    receipt_number: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel: Mapped[str] = mapped_column(String(24), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(160), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    received_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Corrections preserve the immutable original row and exclude it from live
    # totals only after this audit metadata is set. The amount never changes.
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class BrokerCommission(TenantOwned, Base):
    """Referral/broker payout tied to a sale booking."""

    __tablename__ = "broker_commissions"
    __table_args__ = (
        CheckConstraint("amount_paise >= 0", name="commission_amount_non_negative"),
        Index("ix_broker_commissions_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    sale_booking_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sale_bookings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    broker_name: Mapped[str] = mapped_column(String(255), nullable=False)
    broker_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    basis: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CommissionStatus.PENDING.value,
        server_default=CommissionStatus.PENDING.value,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
