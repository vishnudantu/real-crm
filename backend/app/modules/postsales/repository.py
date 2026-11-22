"""Tenant-scoped persistence for the post-sales pack."""

from __future__ import annotations

import hashlib
from datetime import date
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.modules.postsales.models import (
    BrokerCommission,
    Installment,
    InstallmentStatus,
    PaymentPlan,
    Receipt,
    SaleBooking,
    SaleStatus,
)

OPEN_INSTALLMENT_STATUSES = (
    InstallmentStatus.PENDING.value,
    InstallmentStatus.DUE.value,
    InstallmentStatus.PART_PAID.value,
    InstallmentStatus.OVERDUE.value,
)


def live_receipt_conditions():
    """Predicates that keep voided rows out of every live money total.

    Voided receipts remain physically present for audit; only their
    contribution to balances disappears.
    """

    return (Receipt.voided_at.is_(None),)


def get_booking(
    session: Session, booking_id: UUID, *, tenant_id: UUID
) -> SaleBooking | None:
    return session.scalar(
        select(SaleBooking)
        .options(
            selectinload(SaleBooking.plans).selectinload(PaymentPlan.installments)
        )
        .where(SaleBooking.id == booking_id, SaleBooking.tenant_id == tenant_id)
    )


def get_booking_by_lead(
    session: Session, lead_id: UUID, *, tenant_id: UUID
) -> SaleBooking | None:
    return session.scalar(
        select(SaleBooking).where(
            SaleBooking.lead_id == lead_id, SaleBooking.tenant_id == tenant_id
        )
    )


def list_bookings(
    session: Session,
    *,
    tenant_id: UUID,
    offset: int,
    limit: int,
    status: str | None = None,
    project_id: UUID | None = None,
    search: str | None = None,
    newest_first: bool = True,
) -> tuple[list[SaleBooking], int]:
    conditions = [SaleBooking.tenant_id == tenant_id]
    if status is not None:
        conditions.append(SaleBooking.status == status)
    if project_id is not None:
        conditions.append(SaleBooking.project_id == project_id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        conditions.append(SaleBooking.unit_number.ilike(term))
    total = int(
        session.scalar(
            select(func.count()).select_from(SaleBooking).where(*conditions)
        )
        or 0
    )
    order = SaleBooking.created_at.desc() if newest_first else SaleBooking.created_at.asc()
    rows = list(
        session.scalars(
            select(SaleBooking)
            .options(
                selectinload(SaleBooking.plans).selectinload(PaymentPlan.installments)
            )
            .where(*conditions)
            .order_by(order, SaleBooking.id)
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return rows, total


def get_plan(session: Session, plan_id: UUID, *, tenant_id: UUID) -> PaymentPlan | None:
    return session.scalar(
        select(PaymentPlan)
        .options(selectinload(PaymentPlan.installments))
        .where(PaymentPlan.id == plan_id, PaymentPlan.tenant_id == tenant_id)
    )


def get_installment(
    session: Session, installment_id: UUID, *, tenant_id: UUID
) -> Installment | None:
    return session.scalar(
        select(Installment).where(
            Installment.id == installment_id, Installment.tenant_id == tenant_id
        )
    )


def receipt_total_for_installment(
    session: Session, installment_id: UUID, *, tenant_id: UUID
) -> int:
    return int(
        session.scalar(
            select(func.coalesce(func.sum(Receipt.amount_paise), 0)).where(
                Receipt.installment_id == installment_id,
                Receipt.tenant_id == tenant_id,
                *live_receipt_conditions(),
            )
        )
        or 0
    )


def highest_receipt_sequence(session: Session, *, tenant_id: UUID) -> int:
    """Largest numeric suffix already issued in this tenant.

    Derives the next receipt number from MAX rather than COUNT so that voided or
    deleted rows cannot cause a reissued duplicate number. Callers must hold the
    tenant receipt lock. Legacy rows whose number does not match the
    ``RCPT-<digits>`` shape are ignored for the max but remain in place.
    """

    rows = session.scalars(
        select(Receipt.receipt_number).where(Receipt.tenant_id == tenant_id)
    ).all()
    highest = 0
    for number in rows:
        prefix, _, digits = (number or "").rpartition("-")
        if prefix == "RCPT" and digits.isdigit():
            highest = max(highest, int(digits))
    return highest


def lock_receipt_allocation(session: Session, *, tenant_id: UUID) -> None:
    """Serialize receipt numbering and installment balance updates.

    PostgreSQL uses a transaction-scoped advisory lock keyed by tenant, so
    concurrent posts across connections allocate distinct numbers and see
    committed balances. SQLite (isolated test suite) has no advisory locks; the
    caller's in-process lock plus a single shared connection serializes it.
    """

    if session.get_bind().dialect.name != "postgresql":
        return
    digest = hashlib.blake2b(f"receipts:{tenant_id}".encode(), digest_size=8).digest()
    session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": int.from_bytes(digest, "big", signed=True)},
    )


def get_receipt(
    session: Session, receipt_id: UUID, *, tenant_id: UUID
) -> Receipt | None:
    return session.scalar(
        select(Receipt).where(Receipt.id == receipt_id, Receipt.tenant_id == tenant_id)
    )


def get_receipt_by_idempotency_key(
    session: Session, *, tenant_id: UUID, idempotency_key: str
) -> Receipt | None:
    return session.scalar(
        select(Receipt).where(
            Receipt.tenant_id == tenant_id,
            Receipt.idempotency_key == idempotency_key,
        )
    )


def paid_map_for_plan(
    session: Session, plan_ids: list[UUID], *, tenant_id: UUID
) -> dict[UUID, int]:
    if not plan_ids:
        return {}
    rows = session.execute(
        select(Receipt.installment_id, func.coalesce(func.sum(Receipt.amount_paise), 0))
        .join(Installment, Installment.id == Receipt.installment_id)
        .where(
            Installment.plan_id.in_(plan_ids),
            Receipt.tenant_id == tenant_id,
            Installment.tenant_id == tenant_id,
            *live_receipt_conditions(),
        )
        .group_by(Receipt.installment_id)
    ).all()
    return {row[0]: int(row[1] or 0) for row in rows}


def get_commission(
    session: Session, commission_id: UUID, *, tenant_id: UUID
) -> BrokerCommission | None:
    return session.scalar(
        select(BrokerCommission).where(
            BrokerCommission.id == commission_id,
            BrokerCommission.tenant_id == tenant_id,
        )
    )


def list_commissions(
    session: Session, *, tenant_id: UUID, sale_booking_id: UUID
) -> list[BrokerCommission]:
    return list(
        session.scalars(
            select(BrokerCommission)
            .where(
                BrokerCommission.tenant_id == tenant_id,
                BrokerCommission.sale_booking_id == sale_booking_id,
            )
            .order_by(BrokerCommission.created_at.desc())
        ).all()
    )


def refresh_overdue(session: Session, *, tenant_id: UUID, today: date) -> int:
    """Mark open installments past due as OVERDUE. Returns rows updated."""

    rows = session.scalars(
        select(Installment).where(
            Installment.tenant_id == tenant_id,
            Installment.status.in_(
                (
                    InstallmentStatus.PENDING.value,
                    InstallmentStatus.DUE.value,
                )
            ),
            Installment.due_on < today,
        )
    ).all()
    for row in rows:
        row.status = InstallmentStatus.OVERDUE.value
    return len(rows)


TERMINAL_SALE_STATUSES = (SaleStatus.CLOSED.value, SaleStatus.CANCELLED.value)
