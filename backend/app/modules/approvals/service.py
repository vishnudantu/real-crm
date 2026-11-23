"""Approval lifecycle transitions with wired entity side effects.

The ApprovalRequest row is the audit record. Wired (request_type,
reference_type) pairs additionally mutate the referenced entity inside the
SAME transaction as the decision or cancellation (see side_effects.py), so the
decision and its effect commit together or not at all. Unwired pairs keep the
original audit-only behaviour.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.modules.approvals import side_effects
from app.modules.approvals.exceptions import (
    ApprovalAmountInvalidError,
    ApprovalApproverNotFoundError,
    ApprovalCancellationForbiddenError,
    ApprovalDecisionForbiddenError,
    ApprovalRequestNotFoundError,
    ApprovalRequestNotPendingError,
    SelfApprovalError,
)
from app.modules.approvals.models import ApprovalRequest, ApprovalStatus
from app.modules.approvals.side_effects import (
    BOOKING_REFERENCE_TYPE,
    DISCOUNT_REQUEST_TYPE,
    SITE_VISIT_CAR_REQUEST_TYPE,
    UNIT_REFERENCE_TYPE,
    dispatch_cancel,
    dispatch_decision,
)
from app.modules.bookings.exceptions import (
    BookingNotFoundError,
    CarRequestAlreadyRequestedError,
)
from app.modules.bookings.models import Booking, CarRequestStatus
from app.modules.inventory.exceptions import (
    DiscountAlreadyRequestedError,
    UnitNotFoundError,
)
from app.modules.inventory.models import DiscountStatus, PropertyUnit
from app.modules.users import repository as users_repository
from app.modules.users.exceptions import InsufficientPermissionsError
from app.modules.users.models import RoleName, User

DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200
DEMAND_LETTER_REQUEST_TYPE = "DEMAND_LETTER"


def _dispatch_demand_letter_decision(
    session: Session, *, actor: User, request: ApprovalRequest, decision: str, note: str | None
) -> None:
    """Apply the P0.3 release/void side effect for an approved demand letter.

    The approval row itself is the evidence; the referenced document carries
    the gate state. A REJECT voids the letter with the decision note, and no
    outbox event is queued. Failures here must not roll the recorded decision
    back silently — the error propagates after the decision commit.
    """

    if request.reference_type != "document":
        return
    from app.modules.documents import service as document_service

    if decision == ApprovalStatus.APPROVED.value:
        document_service.release_demand_letter(session, actor=actor, document_id=request.reference_id)
    else:
        document_service.reject_demand_letter(
            session,
            actor=actor,
            document_id=request.reference_id,
            reason=note or "Demand letter rejected without a note.",
        )

# The 20%-of-price cap needs a unit price; PropertyUnit carries none, so
# discount validation at creation is positivity only. If a price column is
# ever added, enforce ``0 < amount <= price * 0.20`` here and in the handler.
MAX_DISCOUNT_FRACTION_OF_PRICE = 0.20


def request_approval(
    session: Session,
    *,
    actor: User,
    request_type: str,
    reference_type: str,
    reference_id: UUID,
    reason: str,
    amount_paise: int | None = None,
    approver_id: UUID | None = None,
    commit: bool = True,
) -> ApprovalRequest:
    """Create a pending request in the actor's tenant without entity side effects.

    ``commit=False`` defers the commit to the caller so a wired creator can
    write the request and its entity flag in ONE transaction; the row is
    flushed so its identity and constraints are validated immediately.
    """

    if approver_id is not None:
        approver = users_repository.get_user_by_id(
            session, approver_id, tenant_id=actor.tenant_id
        )
        if (
            approver is None
            or not approver.is_active
            or approver.role.name != RoleName.ADMIN.value
        ):
            raise ApprovalApproverNotFoundError()
    request = ApprovalRequest(
        tenant_id=actor.tenant_id,
        request_type=request_type,
        reference_type=reference_type,
        reference_id=reference_id,
        requested_by_id=actor.id,
        approver_id=approver_id,
        status=ApprovalStatus.PENDING.value,
        amount_paise=amount_paise,
        reason=reason,
    )
    session.add(request)
    session.flush()
    if commit:
        session.commit()
        session.refresh(request)
    return request


def _filtered(
    session: Session,
    tenant_id: UUID,
    status: str | None,
    request_type: str | None,
):
    statement = select(ApprovalRequest).where(ApprovalRequest.tenant_id == tenant_id)
    if status is not None:
        statement = statement.where(ApprovalRequest.status == status)
    if request_type is not None:
        statement = statement.where(ApprovalRequest.request_type == request_type)
    return statement


def count_requests(
    session: Session,
    tenant_id: UUID,
    status: str | None = None,
    request_type: str | None = None,
) -> int:
    """Count the tenant's requests matching the optional filters."""

    statement = (
        select(func.count(ApprovalRequest.id))
        .select_from(ApprovalRequest)
        .where(ApprovalRequest.tenant_id == tenant_id)
    )
    if status is not None:
        statement = statement.where(ApprovalRequest.status == status)
    if request_type is not None:
        statement = statement.where(ApprovalRequest.request_type == request_type)
    return session.scalar(statement) or 0


def list_requests(
    session: Session,
    tenant_id: UUID,
    status: str | None = None,
    request_type: str | None = None,
    limit: int = DEFAULT_LIST_LIMIT,
    offset: int = 0,
) -> list[ApprovalRequest]:
    """Return a newest-first page of requests owned by the supplied tenant."""

    statement = (
        _filtered(session, tenant_id, status, request_type)
        .order_by(ApprovalRequest.created_at.desc(), ApprovalRequest.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(session.scalars(statement).unique().all())


def _get_request(session: Session, *, actor: User, request_id: UUID) -> ApprovalRequest:
    request = session.query(ApprovalRequest).filter_by(
        id=request_id, tenant_id=actor.tenant_id
    ).one_or_none()
    if request is None:
        raise ApprovalRequestNotFoundError()
    return request


def _transition(
    session: Session, request: ApprovalRequest, *, values: dict
) -> ApprovalRequest:
    """Apply a PENDING-guarded update so a concurrent decision cannot overwrite.

    The caller's side-effect mutations are flushed into the same transaction;
    one commit publishes the status flip and the entity change atomically.
    """

    result = session.execute(
        update(ApprovalRequest)
        .where(
            ApprovalRequest.id == request.id,
            ApprovalRequest.tenant_id == request.tenant_id,
            ApprovalRequest.status == ApprovalStatus.PENDING.value,
        )
        .values(**values)
    )
    if result.rowcount == 0:
        session.rollback()
        raise ApprovalRequestNotPendingError()
    session.commit()
    session.refresh(request)
    return request


def decide(
    session: Session,
    *,
    actor: User,
    request_id: UUID,
    decision: str,
    note: str | None = None,
) -> ApprovalRequest:
    """Record a manager's decision and apply any wired side effect.

    Wired pairs (site-visit car, unit discount) run their side effect BEFORE
    the guarded status flip so both publish in one transaction; a missing
    entity raises 400 before anything is decided. The demand-letter pair is
    handled after the decision commit instead (deliberate design: the approval
    evidence survives even if a release/void side effect is retried).
    """

    if decision not in (ApprovalStatus.APPROVED.value, ApprovalStatus.REJECTED.value):
        raise ValueError("decision must be APPROVED or REJECTED")
    if actor.role.name != RoleName.ADMIN.value:
        raise ApprovalDecisionForbiddenError()
    request = _get_request(session, actor=actor, request_id=request_id)
    if request.status != ApprovalStatus.PENDING.value:
        raise ApprovalRequestNotPendingError()
    if request.requested_by_id == actor.id:
        raise SelfApprovalError()
    decided_at = datetime.now(UTC)
    # Wired pairs: side effect first, validating the entity exists BEFORE the
    # guarded update; both flush into one transaction that _transition commits.
    dispatch_decision(session, request=request, decision=decision)
    decided = _transition(
        session,
        request,
        values={
            "status": decision,
            "decision_note": note,
            "decided_at": decided_at,
            "updated_at": decided_at,
            "approver_id": actor.id,
        },
    )
    if request.request_type == DEMAND_LETTER_REQUEST_TYPE:
        _dispatch_demand_letter_decision(
            session, actor=actor, request=decided, decision=decision, note=note
        )
    return decided


def cancel(session: Session, *, actor: User, request_id: UUID) -> ApprovalRequest:
    """Cancel a pending request for its requester or an administrator.

    Wired pairs revert their entity flag in the same transaction.
    """

    request = _get_request(session, actor=actor, request_id=request_id)
    is_requester = request.requested_by_id == actor.id
    is_admin = actor.role.name == RoleName.ADMIN.value
    if not is_requester and not is_admin:
        raise ApprovalCancellationForbiddenError()
    if request.status != ApprovalStatus.PENDING.value:
        raise ApprovalRequestNotPendingError()
    dispatch_cancel(session, request=request)
    return _transition(
        session,
        request,
        values={
            "status": ApprovalStatus.CANCELLED.value,
            "updated_at": datetime.now(UTC),
        },
    )


# ---------------------------------------------------------------------------
# Wired flow creation: request + entity flag in one transaction
# ---------------------------------------------------------------------------


def _validate_discount_amount(
    session: Session, *, unit, amount_paise: int
) -> None:
    """A discount must be positive and, once units carry a price, capped at 20%.

    PropertyUnit has no price column today, so the cap is inert; the check is
    written so adding a price column only needs the price lookup wired in.
    """

    if amount_paise <= 0:
        raise ApprovalAmountInvalidError()
    price_paise = getattr(unit, "price_paise", None)
    if price_paise is not None and amount_paise > price_paise * MAX_DISCOUNT_FRACTION_OF_PRICE:
        raise ApprovalAmountInvalidError()


def request_booking_car(
    session: Session,
    *,
    actor: User,
    booking_id: UUID,
    reason: str,
    approver_id: UUID | None = None,
) -> ApprovalRequest:
    """Open a SITE_VISIT_CAR approval and flag the booking PENDING atomically.

    Sales executives may raise this only for bookings they can see (admin,
    or assigned to the booking's lead); buyers are always rejected.
    """

    if actor.role.name == RoleName.BUYER.value:
        raise InsufficientPermissionsError()
    booking = session.query(Booking).filter_by(
        id=booking_id, tenant_id=actor.tenant_id
    ).one_or_none()
    if booking is None:
        # Cross-tenant and deleted bookings are indistinguishable: 404.
        raise BookingNotFoundError()
    if actor.role.name == RoleName.SALES_EXECUTIVE.value:
        if (
            booking.executive_id != actor.id
            and (
                booking.lead.current_assignment is None
                or booking.lead.current_assignment.executive_id != actor.id
            )
        ):
            raise BookingNotFoundError()
    if booking.car_request_status != CarRequestStatus.NONE.value:
        raise CarRequestAlreadyRequestedError()
    request = request_approval(
        session,
        actor=actor,
        request_type=SITE_VISIT_CAR_REQUEST_TYPE,
        reference_type=BOOKING_REFERENCE_TYPE,
        reference_id=booking.id,
        reason=reason,
        approver_id=approver_id,
        commit=False,
    )
    booking.car_request_status = CarRequestStatus.PENDING.value
    booking.updated_at = datetime.now(UTC)
    session.add(booking)
    # ONE commit publishes the approval request and the booking flag together.
    session.commit()
    session.refresh(booking)
    session.refresh(request)
    return request


def request_unit_discount(
    session: Session,
    *,
    actor: User,
    unit_id: UUID,
    amount_paise: int,
    reason: str,
    approver_id: UUID | None = None,
) -> ApprovalRequest:
    """Open a DISCOUNT approval carrying amount_paise and flag the unit PENDING.

    Sales executives may propose a discount on any unit in their tenant;
    buyers are always rejected. The amount is validated (> 0, and capped at
    20% of price once units carry one) before anything is written.
    """

    if actor.role.name == RoleName.BUYER.value:
        raise InsufficientPermissionsError()
    unit = session.query(PropertyUnit).filter_by(
        id=unit_id, tenant_id=actor.tenant_id
    ).one_or_none()
    if unit is None:
        # Cross-tenant and deleted units are indistinguishable: 404.
        raise UnitNotFoundError()
    _validate_discount_amount(session, unit=unit, amount_paise=amount_paise)
    if unit.discount_status != DiscountStatus.NONE.value:
        raise DiscountAlreadyRequestedError()
    request = request_approval(
        session,
        actor=actor,
        request_type=DISCOUNT_REQUEST_TYPE,
        reference_type=UNIT_REFERENCE_TYPE,
        reference_id=unit.id,
        reason=reason,
        amount_paise=amount_paise,
        approver_id=approver_id,
        commit=False,
    )
    unit.discount_status = DiscountStatus.PENDING.value
    unit.updated_at = datetime.now(UTC)
    session.add(unit)
    # ONE commit publishes the approval request and the unit flag together.
    session.commit()
    session.refresh(unit)
    session.refresh(request)
    return request
