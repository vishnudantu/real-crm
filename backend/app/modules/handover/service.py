"""Readiness and possession domain rules for handover cases.

Readiness has five equally weighted gates: signed agreement, live money,
recorded registration, a possession date, and independently verified snags.
The score is always recomputed from source rows; the case JSON is only a
completion-time snapshot. All resource lookups include tenant ownership.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.buyer_docs.service import resolve_buyer_contact
from app.modules.customers.models import Opportunity
from app.modules.handover.models import HandoverCase, HandoverStatus, KeyHandover, SnagItem, SnagStatus
from app.modules.handover.schemas import (
    HandoverCaseCreate, HandoverCasePatch, HandoverChecklist, KeyCollect, KeyCreate, KeyPatch,
    SnagCreate, SnagPatch,
)
from app.modules.inventory.models import PropertyUnit
from app.modules.postsales.cancellation import _collected_paise
from app.modules.postsales.models import SaleBooking, SaleStatus
from app.modules.settings.models import AuditLog
from app.modules.users.models import User

COMPLETION_EVENT = "handover.completed"
REQUIRED_CONDITION_COUNT = 5
AGREEMENT_STATUSES = frozenset({
    SaleStatus.AGREEMENT_SIGNED.value,
    SaleStatus.PAYMENTS_IN_PROGRESS.value,
    SaleStatus.POSSESSION_READY.value,
    SaleStatus.CLOSED.value,
})


def _not_found(resource: str = "Handover") -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{resource} not found.")


def _conflict(message: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, message)


def get_case(session: Session, *, tenant_id: UUID, case_id: UUID) -> HandoverCase:
    case = session.scalar(select(HandoverCase).where(
        HandoverCase.id == case_id, HandoverCase.tenant_id == tenant_id
    ))
    if case is None:
        raise _not_found("Handover case")
    return case


def get_snag(session: Session, *, tenant_id: UUID, snag_id: UUID) -> SnagItem:
    snag = session.scalar(select(SnagItem).where(
        SnagItem.id == snag_id, SnagItem.tenant_id == tenant_id
    ))
    if snag is None:
        raise _not_found("Snag")
    return snag


def get_key(session: Session, *, tenant_id: UUID, key_id: UUID) -> KeyHandover:
    key = session.scalar(select(KeyHandover).where(
        KeyHandover.id == key_id, KeyHandover.tenant_id == tenant_id
    ))
    if key is None:
        raise _not_found("Key handover")
    return key


def _validate_assignee(session: Session, *, actor: User, user_id: UUID | None) -> None:
    if user_id is None:
        return
    assignee = session.scalar(select(User).where(
        User.id == user_id, User.tenant_id == actor.tenant_id, User.is_active.is_(True)
    ))
    if assignee is None:
        raise _not_found("Assigned staff member")


def _booking(session: Session, case: HandoverCase) -> SaleBooking | None:
    if case.booking_id is None:
        return None
    return session.scalar(select(SaleBooking).where(
        SaleBooking.id == case.booking_id, SaleBooking.tenant_id == case.tenant_id
    ))


def list_cases(session: Session, *, tenant_id: UUID, status_filter: str | None = None) -> list[dict]:
    query = (
        select(HandoverCase, PropertyUnit.internal_code, SaleBooking.unit_number)
        .join(PropertyUnit, PropertyUnit.id == HandoverCase.unit_id)
        .outerjoin(SaleBooking, (SaleBooking.id == HandoverCase.booking_id) & (SaleBooking.tenant_id == tenant_id))
        .where(HandoverCase.tenant_id == tenant_id, PropertyUnit.tenant_id == tenant_id)
    )
    if status_filter is not None:
        query = query.where(HandoverCase.status == status_filter)
    rows = session.execute(query.order_by(HandoverCase.created_at.desc(), HandoverCase.id)).all()
    return [
        {**case.__dict__, "unit_number": unit_number, "booking_reference": booking_reference}
        for case, unit_number, booking_reference in rows
    ]


def create_case(session: Session, *, actor: User, payload: HandoverCaseCreate) -> HandoverCase:
    unit = session.scalar(select(PropertyUnit).where(
        PropertyUnit.id == payload.unit_id, PropertyUnit.tenant_id == actor.tenant_id
    ))
    if unit is None:
        raise _not_found("Property unit")
    if payload.booking_id is not None:
        booking = session.scalar(select(SaleBooking).where(
            SaleBooking.id == payload.booking_id, SaleBooking.tenant_id == actor.tenant_id
        ))
        if booking is None or booking.unit_id != unit.id:
            raise _not_found("Sale booking for unit")
    case = HandoverCase(
        tenant_id=actor.tenant_id,
        **payload.model_dump(),
    )
    session.add(case)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise _conflict("This unit already has a handover case.") from exc
    session.refresh(case)
    return case


def update_case(session: Session, *, actor: User, case_id: UUID, payload: HandoverCasePatch) -> HandoverCase:
    case = get_case(session, tenant_id=actor.tenant_id, case_id=case_id)
    _require_not_handed_over(case)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(case, field, value)
    session.add_all([
        AuditLog(
            tenant_id=actor.tenant_id, action="UPDATE_HANDOVER_CHECKLIST",
            actor_id=actor.id, actor_name=actor.full_name, actor_email=actor.email,
            resource_type="HANDOVER_CASE", resource_id=str(case.id),
            details={
                "registration_date": case.registration_date.isoformat() if case.registration_date else None,
                "registration_reference": case.registration_reference,
                "possession_date": case.possession_date.isoformat() if case.possession_date else None,
            },
        ),
        case,
    ])
    session.commit()
    session.refresh(case)
    return case


def delete_case(session: Session, *, actor: User, case_id: UUID) -> None:
    from app.modules.bookings import evidence_storage

    case = get_case(session, tenant_id=actor.tenant_id, case_id=case_id)
    _require_not_handed_over(case)
    photo_paths = list(session.scalars(select(SnagItem.photo_evidence_path).where(
        SnagItem.case_id == case.id, SnagItem.photo_evidence_path.is_not(None)
    )).all())
    session.execute(delete(SnagItem).where(SnagItem.case_id == case.id))
    session.execute(delete(KeyHandover).where(KeyHandover.case_id == case.id))
    session.delete(case)
    session.commit()
    for path in photo_paths:
        evidence_storage.remove_evidence(path)


def _financials(session: Session, booking: SaleBooking | None) -> dict:
    if booking is None:
        return {
            "planned_paise": None, "collected_paise": None,
            "outstanding_paise": None, "live_receipt_count": 0,
        }
    collected, planned = _collected_paise(session, booking=booking, tenant_id=booking.tenant_id)
    from app.modules.postsales.models import Installment, PaymentPlan, Receipt

    live_receipt_count = int(session.scalar(
        select(func.count()).select_from(Receipt)
        .join(Installment, Installment.id == Receipt.installment_id)
        .join(PaymentPlan, PaymentPlan.id == Installment.plan_id)
        .where(
            PaymentPlan.sale_booking_id == booking.id,
            Receipt.tenant_id == booking.tenant_id,
            Receipt.voided_at.is_(None),
        )
    ) or 0)
    return {
        "planned_paise": planned,
        "collected_paise": collected,
        "outstanding_paise": max(0, planned - collected),
        "live_receipt_count": live_receipt_count,
    }


def build_checklist(session: Session, *, tenant_id: UUID, case_id: UUID) -> dict:
    """Return honest live readiness, including every unmet required condition."""

    case = get_case(session, tenant_id=tenant_id, case_id=case_id)
    booking = _booking(session, case)
    financials = _financials(session, booking)
    snag_count = int(session.scalar(select(func.count()).select_from(SnagItem).where(
        SnagItem.case_id == case.id, SnagItem.tenant_id == tenant_id,
    )) or 0)
    unresolved_snags = int(session.scalar(select(func.count()).select_from(SnagItem).where(
        SnagItem.case_id == case.id, SnagItem.tenant_id == tenant_id,
        SnagItem.status.not_in((SnagStatus.VERIFIED.value, SnagStatus.CLOSED.value)),
    )) or 0)
    agreement_met = booking is not None and (
        booking.status in AGREEMENT_STATUSES or booking.agreement_date is not None
    )
    possession_date = case.possession_date or (booking.expected_possession if booking else None)
    outstanding = financials["outstanding_paise"]
    conditions = [
        {"code": "AGREEMENT", "label": "Agreement signed", "met": agreement_met,
         "detail": "Agreement is signed." if agreement_met else "A signed sale agreement is required."},
        {"code": "FINANCIALS", "label": "Financials cleared", "met": outstanding == 0,
         "detail": "Live outstanding balance is zero." if outstanding == 0 else
         (f"Outstanding balance: {outstanding} paise (voided receipts excluded)." if outstanding is not None else "No linked booking ledger is available.")},
        {"code": "REGISTRATION", "label": "Registration recorded", "met": case.registration_date is not None,
         "detail": f"Registered on {case.registration_date}." if case.registration_date else "Record the registration date before possession."},
        {"code": "POSSESSION", "label": "Possession date recorded", "met": possession_date is not None,
         "detail": f"Possession date: {possession_date}." if possession_date else "Record an expected or actual possession date."},
        {"code": "SNAGS", "label": "Snags independently verified", "met": unresolved_snags == 0,
         "detail": "No open snags; all resolved snags are independently verified." if unresolved_snags == 0 else f"{unresolved_snags} snag(s) need fixing or independent verification."},
    ]
    if booking is None:
        blockers = [{
            "code": "BOOKING", "label": "Linked sale booking",
            "detail": "Link a sale booking to assess agreement, money and possession.",
            "required_count": REQUIRED_CONDITION_COUNT,
        }]
        for condition in conditions:
            condition["met"] = False
        score = 0
    else:
        blockers = [
            {**condition, "required_count": REQUIRED_CONDITION_COUNT}
            for condition in conditions if not condition["met"]
        ]
        met_count = sum(condition["met"] for condition in conditions)
        score = int((Decimal(100 * met_count) / REQUIRED_CONDITION_COUNT).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return {
        "case_id": case.id, "score": score,
        "required_count": REQUIRED_CONDITION_COUNT,
        "met_count": sum(condition["met"] for condition in conditions),
        "conditions": conditions, "blockers": blockers, "financials": financials,
        "snag_count": snag_count, "unresolved_snag_count": unresolved_snags, "checked_at": datetime.now(UTC),
    }


def _require_not_handed_over(case: HandoverCase) -> None:
    if case.status == HandoverStatus.HANDED_OVER.value:
        raise _conflict("A handed-over case cannot be modified.")


def create_snag(session: Session, *, actor: User, case_id: UUID, payload: SnagCreate) -> SnagItem:
    case = get_case(session, tenant_id=actor.tenant_id, case_id=case_id)
    _require_not_handed_over(case)
    _validate_assignee(session, actor=actor, user_id=payload.assigned_user_id)
    snag = SnagItem(tenant_id=actor.tenant_id, case_id=case.id, **payload.model_dump())
    session.add(snag)
    case.status = HandoverStatus.SNAG_OPEN.value
    session.commit()
    session.refresh(snag)
    return snag


def list_snags(session: Session, *, tenant_id: UUID, case_id: UUID) -> list[SnagItem]:
    case = get_case(session, tenant_id=tenant_id, case_id=case_id)
    return list(session.scalars(select(SnagItem).where(
        SnagItem.case_id == case.id, SnagItem.tenant_id == tenant_id
    ).order_by(SnagItem.created_at, SnagItem.id)).all())


def update_snag(session: Session, *, actor: User, snag_id: UUID, payload: SnagPatch) -> SnagItem:
    snag = get_snag(session, tenant_id=actor.tenant_id, snag_id=snag_id)
    _require_not_handed_over(get_case(session, tenant_id=actor.tenant_id, case_id=snag.case_id))
    if snag.status != SnagStatus.OPEN.value:
        raise _conflict("Only an open snag can be edited.")
    _validate_assignee(session, actor=actor, user_id=payload.assigned_user_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(snag, field, value)
    session.commit()
    session.refresh(snag)
    return snag


def transition_snag(session: Session, *, actor: User, snag_id: UUID, action: str) -> SnagItem:
    snag = get_snag(session, tenant_id=actor.tenant_id, snag_id=snag_id)
    case = get_case(session, tenant_id=actor.tenant_id, case_id=snag.case_id)
    _require_not_handed_over(case)
    expected = {"fix": SnagStatus.OPEN, "verify": SnagStatus.FIXED, "close": SnagStatus.VERIFIED}.get(action)
    if expected is None or snag.status != expected.value:
        raise _conflict(f"A snag must be {expected.value if expected else 'in a valid state'} before {action}.")
    now = datetime.now(UTC)
    if action == "fix":
        snag.status = SnagStatus.FIXED.value
        snag.fixed_by_id = actor.id
        snag.fixed_at = now
    elif action == "verify":
        if snag.fixed_by_id is not None and snag.fixed_by_id == actor.id:
            raise _conflict("Snag verification requires a different staff member than the fixer.")
        snag.status = SnagStatus.VERIFIED.value
        snag.verified_by_id = actor.id
        snag.verified_at = now
    else:
        snag.status = SnagStatus.CLOSED.value
        snag.closed_at = now
    _refresh_case_status(session, case)
    session.commit()
    session.refresh(snag)
    return snag


def _refresh_case_status(session: Session, case: HandoverCase) -> None:
    if case.status == HandoverStatus.HANDED_OVER.value:
        return
    case.status = derive_case_status(session, case)


def derive_case_status(session: Session, case: HandoverCase) -> str:
    """Derive operational status without ever treating it as readiness proof."""

    if case.status == HandoverStatus.HANDED_OVER.value:
        return HandoverStatus.HANDED_OVER.value
    rows = list(session.scalars(select(SnagItem).where(SnagItem.case_id == case.id)).all())
    if any(snag.status in (SnagStatus.OPEN.value, SnagStatus.FIXED.value) for snag in rows):
        return HandoverStatus.SNAG_OPEN.value
    if rows and all(snag.status in (SnagStatus.VERIFIED.value, SnagStatus.CLOSED.value) for snag in rows):
        return HandoverStatus.READY.value
    return HandoverStatus.IN_PROGRESS.value if rows else case.status


def delete_snag(session: Session, *, actor: User, snag_id: UUID) -> None:
    from app.modules.bookings import evidence_storage

    snag = get_snag(session, tenant_id=actor.tenant_id, snag_id=snag_id)
    case = get_case(session, tenant_id=actor.tenant_id, case_id=snag.case_id)
    _require_not_handed_over(case)
    photo_path = snag.photo_evidence_path
    session.delete(snag)
    session.flush()
    _refresh_case_status(session, case)
    session.commit()
    if photo_path:
        evidence_storage.remove_evidence(photo_path)


def upload_snag_photo(session: Session, *, actor: User, snag_id: UUID, contents: bytes, content_type: str) -> SnagItem:
    from app.modules.bookings import evidence_storage

    snag = get_snag(session, tenant_id=actor.tenant_id, snag_id=snag_id)
    _require_not_handed_over(get_case(session, tenant_id=actor.tenant_id, case_id=snag.case_id))
    if content_type not in evidence_storage.ALLOWED_CONTENT_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported evidence content type.")
    if not contents or len(contents) > evidence_storage.MAX_EVIDENCE_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Evidence must be non-empty and at most 10 MB.")
    path, digest = evidence_storage.write_evidence(tenant_id=actor.tenant_id, contents=contents)
    previous_path = snag.photo_evidence_path
    snag.photo_evidence_path = path
    snag.photo_content_sha256 = digest
    snag.photo_content_type = content_type
    try:
        session.commit()
    except Exception:
        session.rollback()
        evidence_storage.remove_evidence(path)
        raise
    if previous_path:
        evidence_storage.remove_evidence(previous_path)
    session.refresh(snag)
    return snag


def download_snag_photo(session: Session, *, actor: User, snag_id: UUID) -> tuple[SnagItem, Path]:
    from app.modules.bookings import evidence_storage

    snag = get_snag(session, tenant_id=actor.tenant_id, snag_id=snag_id)
    if snag.photo_evidence_path is None:
        raise _not_found("Snag photo")
    try:
        return snag, evidence_storage.resolve_path(snag.photo_evidence_path)
    except ValueError as exc:
        raise _not_found("Snag photo") from exc


def record_keys(session: Session, *, actor: User, case_id: UUID, payload: KeyCreate) -> KeyHandover:
    case = get_case(session, tenant_id=actor.tenant_id, case_id=case_id)
    _require_not_handed_over(case)
    key = KeyHandover(tenant_id=actor.tenant_id, case_id=case.id, **payload.model_dump())
    session.add(key)
    session.commit()
    session.refresh(key)
    return key


def list_keys(session: Session, *, tenant_id: UUID, case_id: UUID) -> list[KeyHandover]:
    case = get_case(session, tenant_id=tenant_id, case_id=case_id)
    return list(session.scalars(select(KeyHandover).where(
        KeyHandover.case_id == case.id, KeyHandover.tenant_id == tenant_id
    ).order_by(KeyHandover.handed_at.desc(), KeyHandover.id)).all())


def update_keys(session: Session, *, actor: User, key_id: UUID, payload: KeyPatch) -> KeyHandover:
    key = get_key(session, tenant_id=actor.tenant_id, key_id=key_id)
    _require_not_handed_over(get_case(session, tenant_id=actor.tenant_id, case_id=key.case_id))
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(key, field, value)
    session.commit()
    session.refresh(key)
    return key


def collect_keys(session: Session, *, actor: User, key_id: UUID, payload: KeyCollect) -> KeyHandover:
    key = get_key(session, tenant_id=actor.tenant_id, key_id=key_id)
    if key.collected_id is not None:
        raise _conflict("This key register entry is already collected.")
    key.collected_id = actor.id
    key.collected_at = datetime.now(UTC)
    key.collected_notes = payload.notes
    session.commit()
    session.refresh(key)
    return key


def delete_keys(session: Session, *, actor: User, key_id: UUID) -> None:
    key = get_key(session, tenant_id=actor.tenant_id, key_id=key_id)
    _require_not_handed_over(get_case(session, tenant_id=actor.tenant_id, case_id=key.case_id))
    session.delete(key)
    session.commit()


def complete_case(session: Session, *, actor: User, case_id: UUID, override_reason: str | None) -> HandoverCase:
    case = get_case(session, tenant_id=actor.tenant_id, case_id=case_id)
    if case.status == HandoverStatus.HANDED_OVER.value:
        raise _conflict("This handover is already complete.")
    checklist = build_checklist(session, tenant_id=actor.tenant_id, case_id=case_id)
    if checklist["score"] < 100 and not override_reason:
        codes = ", ".join(blocker["code"] for blocker in checklist["blockers"])
        raise _conflict(f"Readiness is {checklist['score']}%; blockers: {codes}. A recorded override reason is required.")
    now = datetime.now(UTC)
    if checklist["score"] < 100:
        case.override_reason = override_reason
        case.override_by_id = actor.id
        case.override_at = now
    case.status = HandoverStatus.HANDED_OVER.value
    case.readiness = HandoverChecklist.model_validate(checklist).model_dump(mode="json")
    case.handed_over_at = now
    case.handed_over_by_id = actor.id
    booking = _booking(session, case)
    from app.modules.messaging.engine import emit_event

    emit_event(
        session, tenant_id=actor.tenant_id, event=COMPLETION_EVENT,
        context={
            "entity_type": "handover_case", "entity_id": case.id,
            "unit_number": booking.unit_number if booking else str(case.unit_id),
            "handed_at": now.isoformat(),
            "to_address": _recipient(session, booking),
        },
    )
    from app.modules.settings.service import log_admin_action

    log_admin_action(
        session, actor=actor, action="COMPLETE_HANDOVER", resource_type="HANDOVER_CASE",
        resource_id=str(case.id), details={
            "readiness_score": checklist["score"], "blockers": checklist["blockers"],
            "override_reason": override_reason if checklist["score"] < 100 else None,
        },
    )
    session.commit()
    session.refresh(case)
    return case


def _recipient(session: Session, booking: SaleBooking | None) -> str | None:
    if booking is None:
        return None
    from app.modules.leads.models import Lead

    lead = session.scalar(select(Lead).where(Lead.id == booking.lead_id, Lead.tenant_id == booking.tenant_id))
    return (lead.phone or lead.email) if lead else None


def buyer_download_photo(session: Session, *, actor: User, snag_id: UUID) -> tuple[SnagItem, Path]:
    snag = get_snag(session, tenant_id=actor.tenant_id, snag_id=snag_id)
    cases = buyer_cases(session, actor=actor)
    if not any(snag.id == item.id for case in cases for item in case["snags"]):
        raise _not_found("Snag photo")
    return download_snag_photo(session, actor=actor, snag_id=snag_id)


def buyer_cases(session: Session, *, actor: User) -> list[dict]:
    """Resolve unit ownership through canonical contact opportunities.

    Buyer responses intentionally omit ledger amounts, staff notes, assignment
    details and override evidence. No client-provided contact id is accepted.
    """

    contact = resolve_buyer_contact(session, actor)
    if contact is None:
        raise _not_found("Buyer handover")
    rows = list(session.execute(
        select(HandoverCase, PropertyUnit, SaleBooking)
        .join(PropertyUnit, PropertyUnit.id == HandoverCase.unit_id)
        .join(SaleBooking, SaleBooking.unit_id == PropertyUnit.id)
        .join(Opportunity, Opportunity.lead_id == SaleBooking.lead_id)
        .where(
            HandoverCase.tenant_id == actor.tenant_id,
            Opportunity.tenant_id == actor.tenant_id,
            Opportunity.contact_id == contact.id,
            Opportunity.lead_id.is_not(None),
            Opportunity.project_id == SaleBooking.project_id,
            SaleBooking.tenant_id == actor.tenant_id,
            PropertyUnit.tenant_id == actor.tenant_id,
            SaleBooking.unit_id == HandoverCase.unit_id,
            HandoverCase.booking_id == SaleBooking.id,
        ).order_by(HandoverCase.created_at.desc(), HandoverCase.id)
    ).all())
    if not rows:
        raise _not_found("Buyer handover")
    return [
        {
            "id": case.id, "unit_id": case.unit_id, "unit_number": unit.internal_code,
            "status": case.status, "expected_possession": booking.expected_possession,
            "possession_date": case.possession_date, "handed_over_at": case.handed_over_at,
            "snags": list_snags(session, tenant_id=actor.tenant_id, case_id=case.id),
        }
        for case, unit, booking in rows
    ]
