"""Approval lifecycle transitions; referenced entities are intentionally untouched."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.modules.approvals.exceptions import (
    ApprovalApproverNotFoundError,
    ApprovalCancellationForbiddenError,
    ApprovalDecisionForbiddenError,
    ApprovalRequestNotFoundError,
    ApprovalRequestNotPendingError,
    SelfApprovalError,
)
from app.modules.approvals.models import ApprovalRequest, ApprovalStatus
from app.modules.users import repository as users_repository
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
) -> ApprovalRequest:
    """Create a pending request in the actor's tenant without entity side effects."""

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
    """Apply a PENDING-guarded update so a concurrent decision cannot overwrite."""

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
    """Record a manager's decision and run its request-type side effect.

    The decision row is committed first; the demand-letter release/void then
    joins the same session as its own committed domain transaction so the
    approval evidence survives even if a side effect is retried.
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
    """Cancel a pending request for its requester or an administrator."""

    request = _get_request(session, actor=actor, request_id=request_id)
    is_requester = request.requested_by_id == actor.id
    is_admin = actor.role.name == RoleName.ADMIN.value
    if not is_requester and not is_admin:
        raise ApprovalCancellationForbiddenError()
    if request.status != ApprovalStatus.PENDING.value:
        raise ApprovalRequestNotPendingError()
    return _transition(
        session,
        request,
        values={
            "status": ApprovalStatus.CANCELLED.value,
            "updated_at": datetime.now(UTC),
        },
    )
