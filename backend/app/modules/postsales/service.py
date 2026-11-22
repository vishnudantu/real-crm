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
    ReceiptAlreadyVoidedError,
    ReceiptAmountExceedsOutstandingError,
    ReceiptNotFoundError,
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
    InstallmentUpdateRequest,
    PaymentPlanCreateRequest,
    ReceiptCreateRequest,
    ReceiptVoidRequest,
    SaleBookingCreateRequest,
    SaleBookingUpdateRequest,
)

# SQLite (isolated test/dev suite) has no cross-process advisory locks; this
# in-process lock serializes receipt posting there. PostgreSQL uses the
# transaction-scoped pg_advisory_xact_lock instead.
_receipt_post_lock = Lock()


def _status_for_balance(
    installment: Installment, *, paid_paise: int, today: date | None = None
) -> str:
    """Derive the financial state; PART_PAID takes precedence over due dates."""

    if paid_paise >= installment.amount_paise:
        return InstallmentStatus.PAID.value
    if paid_paise > 0:
        return InstallmentStatus.PART_PAID.value
    due_on = installment.due_on
    today = today or date.today()
    if due_on < today:
        return InstallmentStatus.OVERDUE.value
    if due_on == today:
        return InstallmentStatus.DUE.value
    return InstallmentStatus.PENDING.value


def _sync_booking_closure(
    session: Session, *, installment: Installment, tenant_id: UUID
) -> SaleBooking:
    """Reconcile closure after any installment/payment mutation in this transaction."""

    plan = session.get(PaymentPlan, installment.plan_id)
    booking = (
        repository.get_booking(session, plan.sale_booking_id, tenant_id=tenant_id)
        if plan is not None
        else None
    )
    if booking is None:
        raise SaleBookingNotFoundError()
    # record_receipt historically uses autoflush=False; flush explicitly before
    # deciding whether all installments are settled. The plan ids are queried
    # directly because the eagerly-loaded ``booking.plans`` collection can be
    # stale (expire_on_commit=False) when a plan was created in this session.
    session.flush()
    plan_ids = list(
        session.scalars(
            select(PaymentPlan.id).where(
                PaymentPlan.sale_booking_id == booking.id,
                PaymentPlan.tenant_id == tenant_id,
            )
        ).all()
    )
    open_rows = (
        session.scalars(
            select(Installment).where(
                Installment.plan_id.in_(plan_ids),
                Installment.status.in_(repository.OPEN_INSTALLMENT_STATUSES),
            )
        ).all()
        if plan_ids
        else []
    )
    if not open_rows:
        booking.status = SaleStatus.CLOSED.value
    elif booking.status == SaleStatus.CLOSED.value:
        # A void that reopens the ledger re-arms the payment workflow. CANCELLED
        # bookings never take this branch: reopen is defined for CLOSED only.
        booking.status = SaleStatus.PAYMENTS_IN_PROGRESS.value
    session.add(booking)
    return booking


def _locked_operation(session: Session, operation):
    """Share the receipt allocation lock with all money/status corrections."""

    if session.get_bind().dialect.name == "sqlite":
        with _receipt_post_lock:
            return operation()
    return operation()


def _void_linked_documents(session: Session, *, actor, receipt: Receipt, reason: str) -> None:
    from app.modules.documents import service as document_service
    from app.modules.documents.models import Document

    # reference_type narrows this to receipt evidence, not the installment's demands.
    documents = session.scalars(
        select(Document).where(
            Document.tenant_id == actor.tenant_id,
            Document.reference_type == "receipt",
            Document.reference_id == receipt.id,
        )
    ).all()
    for document in documents:
        document_service.mark_void(
            session, actor=actor, document_id=document.id, reason=reason, commit=False
        )


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
        from app.modules.inventory import repository as inventory_repository
        from app.modules.inventory.models import PropertyUnit

        # Serialize with inventory delete/edit guards: a direct booking with a
        # unit_id must not slip into the check→commit window of a concurrent
        # unit DELETE and silently null the canonical link.
        inventory_repository.lock_unit_for_hold(
            session, tenant_id=actor.tenant_id, unit_id=payload.unit_id
        )
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

        # Close or retain the booking from the flushed live installment states.
        _sync_booking_closure(
            session, installment=installment, tenant_id=actor.tenant_id
        )
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


def void_receipt(
    session: Session, *, actor, receipt_id: UUID, payload: ReceiptVoidRequest
) -> Receipt:
    """Reverse a posting's financial effect without deleting or editing money.

    Refund netting is future work: a void is not a cash refund and no refund
    module exists yet. Idempotency keys remain globally unique, so a replacement
    posting must use a new key even after this reversal.
    """

    from app.modules.messaging.engine import emit_event

    def _void() -> Receipt:
        repository.lock_receipt_allocation(session, tenant_id=actor.tenant_id)
        receipt = repository.get_receipt(session, receipt_id, tenant_id=actor.tenant_id)
        if receipt is None:
            raise ReceiptNotFoundError()
        if receipt.voided_at is not None:
            raise ReceiptAlreadyVoidedError(receipt.void_reason or "")
        installment = repository.get_installment(
            session, receipt.installment_id, tenant_id=actor.tenant_id
        )
        if installment is None:
            raise InstallmentNotFoundError()
        receipt.voided_at = datetime.now(UTC)
        receipt.voided_by_id = actor.id
        receipt.void_reason = payload.reason
        session.add(receipt)
        session.flush()
        installment.status = _status_for_balance(
            installment,
            paid_paise=repository.receipt_total_for_installment(
                session, installment.id, tenant_id=actor.tenant_id
            ),
        )
        session.add(installment)
        _sync_booking_closure(session, installment=installment, tenant_id=actor.tenant_id)
        _void_linked_documents(session, actor=actor, receipt=receipt, reason=payload.reason)
        emit_event(
            session,
            tenant_id=actor.tenant_id,
            event="receipt.voided",
            context={
                "entity_type": "receipt",
                "entity_id": receipt.id,
                "reason": payload.reason,
            },
        )
        session.commit()
        session.refresh(receipt)
        return receipt

    return _locked_operation(session, _void)


def update_installment(
    session: Session, *, actor, installment_id: UUID, payload: InstallmentUpdateRequest
) -> Installment:
    """Edit an open installment without allowing direct settlement or waiver."""

    def _update() -> Installment:
        repository.lock_receipt_allocation(session, tenant_id=actor.tenant_id)
        installment = repository.get_installment(
            session, installment_id, tenant_id=actor.tenant_id
        )
        if installment is None:
            raise InstallmentNotFoundError()
        fields = payload.model_fields_set
        if payload.status in (InstallmentStatus.PAID, InstallmentStatus.WAIVED):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "PAID requires a receipt posting; WAIVED requires a separate waiver workflow.",
            )
        if installment.status == InstallmentStatus.WAIVED.value:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "A waived installment is corrected by the waiver workflow, not this route.",
            )
        paid = repository.receipt_total_for_installment(
            session, installment.id, tenant_id=actor.tenant_id
        )
        new_amount = payload.amount_paise if "amount_paise" in fields else installment.amount_paise
        if new_amount is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Installment amount cannot be null.")
        if new_amount < paid:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Installment amount cannot be below the live paid total of {paid} paise.",
            )
        if "due_on" in fields:
            if payload.due_on is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Due date cannot be null.")
            installment.due_on = payload.due_on
        installment.amount_paise = new_amount
        financial_edit = bool({"amount_paise", "due_on"} & fields)
        if financial_edit or paid > 0:
            installment.status = _status_for_balance(installment, paid_paise=paid)
        elif "status" in fields and payload.status is not None:
            installment.status = payload.status.value
        session.add(installment)
        _sync_booking_closure(session, installment=installment, tenant_id=actor.tenant_id)
        session.commit()
        session.refresh(installment)
        return installment

    return _locked_operation(session, _update)


def send_demand_letter(session: Session, *, actor, installment_id: UUID) -> Installment:
    """Route the legacy demand-letter send through the P0.3 approval gate.

    BEHAVIOR CHANGE (P0.3): the letter is now *prepared* (document generated in
    PENDING_REVIEW, sibling DEMAND_LETTER ApprovalRequest created) and the
    installment's ``demand_letter_sent_at`` is stamped only when the approval
    gate has been passed. For a fresh installment the send therefore completes
    asynchronously, via POST /approvals/requests/{id}/decision by a second
    admin (self-approval is forbidden). Documents that already cleared the
    gate — the legacy direct-issue path or an earlier approval — are released
    immediately so established issue-then-send sequences keep working.
    The returned object remains the ``Installment``; the generated ``Document``
    is exposed as ``demand_letter_document`` for callers that need its
    number/hash. Artifact generation is the issue event, not a claim of
    provider delivery; the messaging outbox owns dispatch state.
    """

    from app.modules.documents import service as document_service
    from app.modules.documents.models import DocumentReviewState, DocumentStatus

    document, request = document_service.prepare_demand_letter(
        session, actor=actor, installment_id=installment_id
    )
    gate_cleared = request is None and document.status != DocumentStatus.VOIDED.value
    if document.status == DocumentStatus.VOIDED.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Demand letter {document.document_number} was rejected "
            f"({document.void_reason or 'no reason recorded'}); issue a new "
            "template version to re-prepare it.",
        )
    if gate_cleared:
        document_service.release_demand_letter(session, actor=actor, document_id=document.id)

    installment = repository.get_installment(
        session, installment_id, tenant_id=actor.tenant_id
    )
    if installment is None:
        raise InstallmentNotFoundError()
    session.refresh(installment)
    # Transient legacy attribute: response serialization reads mapped columns only.
    installment.__dict__["demand_letter_document"] = document
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
    # Explicit queries: with expire_on_commit=False the identity-mapped
    # booking.plans collection can be stale after a plan is added mid-session.
    plans = list(
        session.scalars(
            select(PaymentPlan)
            .where(PaymentPlan.sale_booking_id == booking.id, PaymentPlan.tenant_id == actor.tenant_id)
            .order_by(PaymentPlan.created_at)
        ).all()
    )
    plan_ids = [p.id for p in plans]
    paid_map = repository.paid_map_for_plan(session, plan_ids, tenant_id=actor.tenant_id)

    installments = (
        list(
            session.scalars(
                select(Installment)
                .where(
                    Installment.plan_id.in_(plan_ids),
                    Installment.tenant_id == actor.tenant_id,
                )
                .order_by(Installment.plan_id, Installment.sequence_no)
            ).all()
        )
        if plan_ids
        else []
    )
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

    collected = sum(r.amount_paise for r in receipts if r.voided_at is None)
    planned = sum(i.amount_paise for i in installments)
    return {
        "booking": booking,
        "plans": plans,
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
