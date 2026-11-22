"""Decision side-effect dispatcher: wired approval flows mutate their entity.

The generic ApprovalRequest stays the audit record. This module maps a
(request_type, reference_type) pair to a handler that applies the entity
mutation inside the SAME database transaction as the decision itself, so an
approval and its effect commit together or not at all.

Wired flows:

- SITE_VISIT_CAR on "booking": APPROVED/REJECTED set booking.car_request_status;
  CANCEL reverts it to NONE.
- DISCOUNT on "unit": APPROVED writes unit.approved_discount_paise and sets
  unit.discount_status; REJECTED sets only discount_status (the amount is never
  written); CANCEL reverts discount_status to NONE.

A missing reference entity raises 400 before any decision is committed. Pairs
without a handler are left untouched, preserving the generic audit-only
behaviour for every other request type.
"""

from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from app.modules.approvals.exceptions import (
    ApprovalAmountInvalidError,
    ApprovalReferenceMissingError,
)
from app.modules.approvals.models import ApprovalRequest, ApprovalStatus

SITE_VISIT_CAR_REQUEST_TYPE = "SITE_VISIT_CAR"
DISCOUNT_REQUEST_TYPE = "DISCOUNT"
BOOKING_REFERENCE_TYPE = "booking"
UNIT_REFERENCE_TYPE = "unit"

DecisionHandler = Callable[..., None]


def _tenant_scoped(model, session: Session, *, entity_id, tenant_id):
    """Fetch one entity scoped to the approval's tenant; cross-tenant is 404-shaped None."""

    return (
        session.query(model).filter_by(id=entity_id, tenant_id=tenant_id).one_or_none()
    )


def _apply_booking_car(
    session: Session, *, request: ApprovalRequest, decision: str
) -> None:
    """Mirror the decision onto the booking's car-request flag."""

    from app.modules.bookings.models import Booking, CarRequestStatus

    booking = _tenant_scoped(
        Booking, session, entity_id=request.reference_id, tenant_id=request.tenant_id
    )
    if booking is None:
        raise ApprovalReferenceMissingError(BOOKING_REFERENCE_TYPE)
    if decision == ApprovalStatus.APPROVED.value:
        booking.car_request_status = CarRequestStatus.APPROVED.value
    else:
        booking.car_request_status = CarRequestStatus.REJECTED.value
    session.add(booking)


def _revert_booking_car(session: Session, *, request: ApprovalRequest) -> None:
    """A cancelled car request leaves the booking with no active request."""

    from app.modules.bookings.models import Booking, CarRequestStatus

    booking = _tenant_scoped(
        Booking, session, entity_id=request.reference_id, tenant_id=request.tenant_id
    )
    if booking is None:
        raise ApprovalReferenceMissingError(BOOKING_REFERENCE_TYPE)
    booking.car_request_status = CarRequestStatus.NONE.value
    session.add(booking)


def _apply_unit_discount(
    session: Session, *, request: ApprovalRequest, decision: str
) -> None:
    """Write the approved discount onto the unit; rejection never writes it.

    Cap rule: a discount must be a positive paise amount. A 20%-of-price cap
    would need a unit price, and PropertyUnit carries no price column, so only
    the positivity rule is enforced (mirrored at request creation).
    """

    from app.modules.inventory.models import DiscountStatus, PropertyUnit

    if request.amount_paise is None or request.amount_paise <= 0:
        raise ApprovalAmountInvalidError()
    unit = _tenant_scoped(
        PropertyUnit, session, entity_id=request.reference_id, tenant_id=request.tenant_id
    )
    if unit is None:
        raise ApprovalReferenceMissingError(UNIT_REFERENCE_TYPE)
    if decision == ApprovalStatus.APPROVED.value:
        unit.approved_discount_paise = request.amount_paise
        unit.discount_status = DiscountStatus.APPROVED.value
    else:
        unit.discount_status = DiscountStatus.REJECTED.value
    session.add(unit)


def _revert_unit_discount(session: Session, *, request: ApprovalRequest) -> None:
    """A cancelled discount request leaves no active request flag on the unit."""

    from app.modules.inventory.models import DiscountStatus, PropertyUnit

    unit = _tenant_scoped(
        PropertyUnit, session, entity_id=request.reference_id, tenant_id=request.tenant_id
    )
    if unit is None:
        raise ApprovalReferenceMissingError(UNIT_REFERENCE_TYPE)
    unit.discount_status = DiscountStatus.NONE.value
    session.add(unit)


DECISION_HANDLERS: dict[tuple[str, str], DecisionHandler] = {
    (SITE_VISIT_CAR_REQUEST_TYPE, BOOKING_REFERENCE_TYPE): _apply_booking_car,
    (DISCOUNT_REQUEST_TYPE, UNIT_REFERENCE_TYPE): _apply_unit_discount,
}

CANCEL_HANDLERS: dict[tuple[str, str], DecisionHandler] = {
    (SITE_VISIT_CAR_REQUEST_TYPE, BOOKING_REFERENCE_TYPE): _revert_booking_car,
    (DISCOUNT_REQUEST_TYPE, UNIT_REFERENCE_TYPE): _revert_unit_discount,
}


def dispatch_decision(
    session: Session, *, request: ApprovalRequest, decision: str
) -> None:
    """Apply the wired side effect for a decision, or nothing for unwired pairs.

    Runs inside the caller's transaction; handlers only mutate and add, the
    caller commits. A missing reference entity raises before any commit.
    """

    handler = DECISION_HANDLERS.get((request.request_type, request.reference_type))
    if handler is None:
        return
    handler(session, request=request, decision=decision)


def dispatch_cancel(session: Session, *, request: ApprovalRequest) -> None:
    """Apply the wired revert for a cancellation, or nothing for unwired pairs."""

    handler = CANCEL_HANDLERS.get((request.request_type, request.reference_type))
    if handler is None:
        return
    handler(session, request=request)
