"""Generic staff approval requests and manager-only decisions."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.approvals import service
from app.modules.approvals.models import ApprovalStatus
from app.modules.approvals.schemas import (
    ApprovalDecisionRequest,
    ApprovalRequestCreate,
    ApprovalRequestListResponse,
    ApprovalRequestResponse,
)
from app.modules.auth.dependencies import AdminUser, require_roles
from app.modules.users.models import RoleName, User

router = APIRouter(prefix="/approvals", tags=["approvals"])

ApprovalStaffUser = Annotated[
    User,
    Depends(require_roles(RoleName.ADMIN, RoleName.SALES_EXECUTIVE)),
]


@router.post("/requests", response_model=ApprovalRequestResponse,
             status_code=status.HTTP_201_CREATED)
def create_request_endpoint(
    payload: ApprovalRequestCreate,
    staff: ApprovalStaffUser,
    db: Annotated[Session, Depends(get_db)],
):
    """Open a pending approval for any entity reference without touching it."""

    return service.request_approval(db, actor=staff, **payload.model_dump())


@router.get("/requests", response_model=ApprovalRequestListResponse)
def list_requests_endpoint(
    staff: ApprovalStaffUser,
    db: Annotated[Session, Depends(get_db)],
    request_status: Annotated[ApprovalStatus | None, Query(alias="status")] = None,
    request_type: Annotated[str | None, Query(max_length=48)] = None,
    limit: Annotated[int, Query(ge=1, le=service.MAX_LIST_LIMIT)] = service.DEFAULT_LIST_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Page the tenant's requests, newest first, filtered by status and type."""

    status_value = request_status.value if request_status is not None else None
    rows = service.list_requests(
        db,
        tenant_id=staff.tenant_id,
        status=status_value,
        request_type=request_type,
        limit=limit,
        offset=offset,
    )
    total = service.count_requests(
        db, tenant_id=staff.tenant_id, status=status_value, request_type=request_type
    )
    return ApprovalRequestListResponse(items=rows, total=total, limit=limit, offset=offset)


@router.post("/requests/{request_id}/decision", response_model=ApprovalRequestResponse)
def decide_request_endpoint(
    request_id: UUID,
    payload: ApprovalDecisionRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    """Record an APPROVED or REJECTED decision made by a manager."""

    return service.decide(
        db,
        actor=admin,
        request_id=request_id,
        decision=payload.decision.value,
        note=payload.note,
    )


@router.post("/requests/{request_id}/cancel", response_model=ApprovalRequestResponse)
def cancel_request_endpoint(
    request_id: UUID,
    staff: ApprovalStaffUser,
    db: Annotated[Session, Depends(get_db)],
):
    """Withdraw a pending request on behalf of its requester."""

    return service.cancel(db, actor=staff, request_id=request_id)
