"""Tenant-scoped persistence for bank transactions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.reconciliation.models import BankTransaction, TransactionStatus


def get_transaction(
    session: Session, transaction_id: UUID, *, tenant_id: UUID
) -> BankTransaction | None:
    return session.scalar(
        select(BankTransaction).where(
            BankTransaction.id == transaction_id, BankTransaction.tenant_id == tenant_id
        )
    )


def get_by_utr(
    session: Session, *, tenant_id: UUID, account_label: str, utr: str
) -> BankTransaction | None:
    return session.scalar(
        select(BankTransaction).where(
            BankTransaction.tenant_id == tenant_id,
            BankTransaction.account_label == account_label,
            BankTransaction.utr == utr,
        )
    )


def list_transactions(
    session: Session,
    *,
    tenant_id: UUID,
    status: str | None = None,
    account_label: str | None = None,
) -> list[BankTransaction]:
    conditions = [BankTransaction.tenant_id == tenant_id]
    if status is not None:
        conditions.append(BankTransaction.status == status)
    if account_label is not None:
        conditions.append(BankTransaction.account_label == account_label)
    return list(
        session.scalars(
            select(BankTransaction)
            .where(*conditions)
            .order_by(BankTransaction.created_at.desc(), BankTransaction.id)
        ).all()
    )


def list_unmatched(session: Session, *, tenant_id: UUID) -> list[BankTransaction]:
    return list_transactions(
        session, tenant_id=tenant_id, status=TransactionStatus.UNMATCHED.value
    )
