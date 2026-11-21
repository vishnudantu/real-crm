"""Tenant-scoped persistence for the post-sales pack."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
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
            )
        )
        or 0
    )


def receipt_count_for_tenant(session: Session, *, tenant_id: UUID) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(Receipt).where(Receipt.tenant_id == tenant_id)
        )
        or 0
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
