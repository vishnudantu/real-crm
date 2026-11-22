"""Bank statement rows ingested for tenant-scoped reconciliation matching."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.tenancy import TenantOwned


class TransactionStatus(StrEnum):
    UNMATCHED = "UNMATCHED"
    MATCHED = "MATCHED"
    IGNORED = "IGNORED"


def utcnow() -> datetime:
    return datetime.now(UTC)


class BankTransaction(TenantOwned, Base):
    """One imported bank statement row, with its reconciliation outcome.

    ``matched_installment_id`` records either a confirmed UTR-exact match or a
    pending unique-amount suggestion (which leaves status UNMATCHED until a
    human confirms). No ledger posting happens here.
    """

    __tablename__ = "bank_transactions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "account_label", "utr", name="uq_bank_transactions_tenant_account_utr"
        ),
        Index("ix_bank_transactions_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    account_label: Mapped[str] = mapped_column(String(64), nullable=False)
    utr: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    txn_date: Mapped[date] = mapped_column(Date, nullable=False)
    payer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payer_detail: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TransactionStatus.UNMATCHED.value,
        server_default=TransactionStatus.UNMATCHED.value,
    )
    matched_installment_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("installments.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    matched_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )
