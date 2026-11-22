"""Post-sales business logic: bookings, plans, demand letters, receipts, brokers."""

from __future__ import annotations

from datetime import UTC, date, datetime
from threading import Lock
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.leads.models import Lead, LeadStatus
from app.modules.postsales import repository
from app.modules.postsales.exceptions import (
    BrokerCommissionNotFoundError,
    InstallmentNotFoundError,
    PaymentPlanAmountMismatchError,
    PaymentPlanNotFoundError,
    ReceiptAmountExceedsOutstandingError,
    SaleBookingExistsError,
    SaleBookingNotFoundError,
)
from app.modules.postsales.models import (
    BrokerCommission,
    CommissionStatus,
    Installment,
    InstallmentStatus,
    PaymentPlan,
    Receipt,
    SaleBooking,
    SaleStatus,
)
from app.modules.postsales.schemas import (
    BrokerCommissionCreateRequest,
    PaymentPlanCreateRequest,
    ReceiptCreateRequest,
    SaleBookingCreateRequest,
    SaleBookingUpdateRequest,
)

# SQLite (isolated test/dev suite) has no cross-process advisory locks; this
# in-process lock serializes receipt posting there. PostgreSQL uses the
# transaction-scoped pg_advisory_xact_lock instead.
_receipt_post_lock = Lock()


def create_booking(
    session: Session, *, actor, payload: SaleBookingCreateRequest, commit: bool = True
) -> SaleBooking:
    """Book a converted lead into a unit; one sale booking per lead.

    ``unit_id`` (optional, PF-010) links to a canonical PropertyUnit in the
    same tenant and project as the lead. ``commit=False`` lets the inventory
    conversion flow share one transaction with the hold and unit updates;
    legacy callers keep the default and get the original behavior.
    """

    lead = session.scalar(
        select(Lead).where(Lead.id == payload.lead_id, Lead.tenant_id == actor.tenant_id)
    )
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead not found.")
    if lead.status != LeadStatus.CONVERTED.value:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Only converted leads can be booked as sales.",
        )
    if repository.get_booking_by_lead(session, lead.id, tenant_id=actor.tenant_id):
        raise SaleBookingExistsError()

    if payload.unit_id is not None:
        from app.modules.inventory.models import PropertyUnit

        unit = session.scalar(
            select(PropertyUnit).where(
                PropertyUnit.id == payload.unit_id,
                PropertyUnit.tenant_id == actor.tenant_id,
            )
        )
        if unit is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit not found.")
        if unit.project_id != lead.project_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "The unit and lead belong to different projects.",
            )

    customer = None
    if lead.email:
        from app.modules.users.models import Role, RoleName, User

        customer = session.scalar(
            select(User)
            .join(Role, Role.id == User.role_id)
            .where(
                User.email == lead.email,
                User.tenant_id == actor.tenant_id,
                Role.name == RoleName.BUYER.value,
            )
        )

    booking = SaleBooking(
        tenant_id=actor.tenant_id,
        lead_id=lead.id,
        project_id=lead.project_id,
        customer_id=customer.id if customer else None,
        unit_number=payload.unit_number,
        unit_id=payload.unit_id,
        configuration=payload.configuration or lead.preferred_configuration,
        carpet_area_sqft=payload.carpet_area_sqft,
        consideration_paise=payload.consideration_paise,
        booked_on=payload.booked_on or date.today(),
        status=SaleStatus.BOOKED.value,
    )
    session.add(booking)
    if commit:
        session.commit()
        session.refresh(booking)
    else:
        session.flush()
    return booking


def update_booking(
    session: Session, *, actor, booking_id: UUID, payload: SaleBookingUpdateRequest
) -> SaleBooking:
    booking = repository.get_booking(session, booking_id, tenant_id=actor.tenant_id)
    if booking is None:
        raise SaleBookingNotFoundError()
    fields = payload.model_fields_set
    if "status" in fields and payload.status is not None:
        booking.status = payload.status.value
    if "agreement_date" in fields and payload.agreement_date is not None:
        booking.agreement_date = payload.agreement_date
    if "expected_possession" in fields and payload.expected_possession is not None:
        booking.expected_possession = payload.expected_possession
    if "unit_number" in fields and payload.unit_number is not None:
        booking.unit_number = payload.unit_number
    if "carpet_area_sqft" in fields and payload.carpet_area_sqft is not None:
        booking.carpet_area_sqft = payload.carpet_area_sqft
    session.add(booking)
    session.commit()
    return booking


def create_plan(
    session: Session, *, actor, booking_id: UUID, payload: PaymentPlanCreateRequest
) -> PaymentPlan:
    """Add a payment plan whose installments sum exactly to the consideration."""

    booking = repository.get_booking(session, booking_id, tenant_id=actor.tenant_id)
    if booking is None:
        raise SaleBookingNotFoundError()
    total = sum(spec.amount_paise for spec in payload.installments)
    if total != booking.consideration_paise:
        raise PaymentPlanAmountMismatchError()

    plan = PaymentPlan(
        tenant_id=actor.tenant_id,
        sale_booking_id=booking.id,
        name=payload.name,
        plan_type=payload.plan_type.value,
    )
    session.add(plan)
    session.flush()
    today = date.today()
    for index, spec in enumerate(payload.installments, start=1):
        initial = (
            InstallmentStatus.OVERDUE
            if spec.due_on < today
            else InstallmentStatus.DUE
            if spec.due_on == today
            else InstallmentStatus.PENDING
        )
        session.add(
            Installment(
                tenant_id=actor.tenant_id,
                plan_id=plan.id,
                sequence_no=index,
                milestone=spec.milestone,
                amount_paise=spec.amount_paise,
                due_on=spec.due_on,
                status=initial.value,
            )
        )
    if booking.status == SaleStatus.BOOKED.value:
        booking.status = SaleStatus.PAYMENTS_IN_PROGRESS.value
    session.commit()
    session.refresh(plan)
    return plan


def record_receipt(
    session: Session,
    *,
    actor,
    payload: ReceiptCreateRequest,
    idempotency_key: str | None = None,
) -> Receipt:
    """Append a payment receipt and update the installment's paid state.

    Concurrency-safe: allocation of the tenant receipt number and the
    installment balance check happen inside one locked critical section —
    ``pg_advisory_xact_lock`` on PostgreSQL (serializes across connections),
    a process lock on SQLite. Duplicate numbers cannot be issued; concurrent
    posts that together exceed the outstanding balance leave exactly one
    winner and one ``ReceiptAmountExceedsOutstandingError`` conflict. Numbers
    are derived from the highest issued sequence, never from a row count, so
    deleted or voided rows can never cause a reissue.

    Idempotent: when ``idempotency_key`` (or ``payload.idempotency_key``) is
    supplied, a repeated request returns the previously posted receipt without
    creating a new ledger entry.
    """

    key = (idempotency_key or payload.idempotency_key or "").strip() or None

    if key:
        existing = repository.get_receipt_by_idempotency_key(
            session, tenant_id=actor.tenant_id, idempotency_key=key
        )
        if existing is not None:
            return existing

    def _post() -> Receipt:
        repository.lock_receipt_allocation(session, tenant_id=actor.tenant_id)

        installment = repository.get_installment(
            session, payload.installment_id, tenant_id=actor.tenant_id
        )
        if installment is None:
            raise InstallmentNotFoundError()
        if installment.status in (
            InstallmentStatus.PAID.value,
            InstallmentStatus.WAIVED.value,
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "This installment is already closed."
            )

        paid = repository.receipt_total_for_installment(
            session, installment.id, tenant_id=actor.tenant_id
        )
        outstanding = installment.amount_paise - paid
        if payload.amount_paise > outstanding:
            raise ReceiptAmountExceedsOutstandingError()

        number = (
            f"RCPT-{repository.highest_receipt_sequence(session, tenant_id=actor.tenant_id) + 1:06d}"
        )
        receipt = Receipt(
            tenant_id=actor.tenant_id,
            installment_id=installment.id,
            receipt_number=number,
            amount_paise=payload.amount_paise,
            channel=payload.channel.value,
            reference=payload.reference,
            idempotency_key=key,
            received_by_id=actor.id,
            paid_at=payload.paid_at or datetime.now(UTC),
            notes=payload.notes,
        )
        session.add(receipt)

        new_paid = paid + payload.amount_paise
        installment.status = (
            InstallmentStatus.PAID.value if new_paid >= installment.amount_paise
            else InstallmentStatus.PART_PAID.value
        )
        session.add(installment)

        # Close the sale booking when every open installment is settled.
        plan = installment.plan
        booking = repository.get_booking(
            session, plan.sale_booking_id, tenant_id=actor.tenant_id
        )
        all_plans = booking.plans
        open_rows = session.scalars(
            select(Installment).where(
                Installment.plan_id.in_([p.id for p in all_plans]),
                Installment.status.notin_(
                    (InstallmentStatus.PAID.value, InstallmentStatus.WAIVED.value)
                ),
            )
        ).all()
        if not open_rows:
            booking.status = SaleStatus.CLOSED.value
            session.add(booking)
        session.commit()
        session.refresh(receipt)
        return receipt

    try:
        if session.get_bind().dialect.name == "sqlite":
            with _receipt_post_lock:
                return _post()
        return _post()
    except IntegrityError:
        # Lost the race against a concurrent commit (duplicate number or a
        # replayed idempotency key inserted first): return the winner or a
        # well-defined conflict. Never leave a partial mutation behind.
        session.rollback()
        if key:
            existing = repository.get_receipt_by_idempotency_key(
                session, tenant_id=actor.tenant_id, idempotency_key=key
            )
            if existing is not None:
                return existing
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This payment posting conflicted with a concurrent one. Retry the request.",
        ) from None


def send_demand_letter(session: Session, *, actor, installment_id: UUID) -> Installment:
    """Mark a demand letter as sent and record the timestamp for follow-up."""

    installment = repository.get_installment(
        session, installment_id, tenant_id=actor.tenant_id
    )
    if installment is None:
        raise InstallmentNotFoundError()
    installment.demand_letter_sent_at = datetime.now(UTC)
    if installment.status in (
        InstallmentStatus.PENDING.value,
        InstallmentStatus.DUE.value,
    ):
        installment.status = InstallmentStatus.DUE.value
    session.add(installment)
    session.commit()
    session.refresh(installment)
    return installment


def create_commission(
    session: Session, *, actor, booking_id: UUID, payload: BrokerCommissionCreateRequest
) -> BrokerCommission:
    booking = repository.get_booking(session, booking_id, tenant_id=actor.tenant_id)
    if booking is None:
        raise SaleBookingNotFoundError()
    row = BrokerCommission(
        tenant_id=actor.tenant_id,
        sale_booking_id=booking.id,
        broker_name=payload.broker_name,
        broker_phone=payload.broker_phone,
        basis=payload.basis,
        amount_paise=payload.amount_paise,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def update_commission(session: Session, *, actor, commission_id: UUID, status_value) -> BrokerCommission:
    row = repository.get_commission(session, commission_id, tenant_id=actor.tenant_id)
    if row is None:
        raise BrokerCommissionNotFoundError()
    row.status = status_value.value
    if status_value == CommissionStatus.PAID:
        row.paid_at = datetime.now(UTC)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def ledger(session: Session, *, actor, booking_id: UUID) -> dict:
    """Return the full financial picture for one sale booking."""

    booking = repository.get_booking(session, booking_id, tenant_id=actor.tenant_id)
    if booking is None:
        raise SaleBookingNotFoundError()
    plan_ids = [p.id for p in booking.plans]
    paid_map = repository.paid_map_for_plan(session, plan_ids, tenant_id=actor.tenant_id)

    installments = [i for p in booking.plans for i in p.installments]
    receipts = list(
        session.scalars(
            select(Receipt).where(
                Receipt.installment_id.in_([i.id for i in installments] or [UUID(int=0)]),
                Receipt.tenant_id == actor.tenant_id,
            ).order_by(Receipt.paid_at.desc())
        ).all()
    ) if installments else []
    commissions = repository.list_commissions(
        session, tenant_id=actor.tenant_id, sale_booking_id=booking.id
    )

    collected = sum(r.amount_paise for r in receipts)
    planned = sum(i.amount_paise for i in installments)
    return {
        "booking": booking,
        "plans": booking.plans,
        "installments": [
            {
                "id": i.id,
                "plan_id": i.plan_id,
                "sequence_no": i.sequence_no,
                "milestone": i.milestone,
                "amount_paise": i.amount_paise,
                "due_on": i.due_on,
                "status": i.status,
                "demand_letter_sent_at": i.demand_letter_sent_at,
                "paid_paise": paid_map.get(i.id, 0),
                "outstanding_paise": i.amount_paise - paid_map.get(i.id, 0),
            }
            for i in installments
        ],
        "receipts": receipts,
        "commissions": commissions,
        "collected_paise": collected,
        "outstanding_paise": max(0, planned - collected),
    }
