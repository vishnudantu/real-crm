"""Inventory API: canonical units, availability, and exclusive holds."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.approvals.schemas import ApprovalRequestResponse
from app.modules.approvals.service import request_unit_discount
from app.modules.auth.dependencies import CurrentUser, ManagerUser, require_roles
from app.modules.inventory import repository, service
from app.modules.inventory.exceptions import UnitNotFoundError
from app.modules.inventory.schemas import (
    AvailabilityResponse,
    BulkUnitCreateRequest,
    BulkUnitCreateResponse,
    DiscountRequestCreateRequest,
    HoldConvertRequest,
    HoldConvertResponse,
    HoldCreateRequest,
    HoldExtendRequest,
    HoldReleaseRequest,
    HoldResponse,
    UnitCreateRequest,
    UnitDetailResponse,
    UnitListResponse,
    UnitResponse,
    UnitStatusEventResponse,
    UnitStatusUpdateRequest,
    UnitUpdateRequest,
)
from app.modules.users.models import RoleName, User

router = APIRouter(prefix="/inventory", tags=["inventory"])

# Permission boundary: MANAGER extends ADMIN/SALES_EXECUTIVE staff access only
# for unit administration and hold workflows here. Project/fact administration,
# unrelated sales workflows, operator impersonation, billing, tenant branding,
# user role management, and feature flags remain on their existing dependencies.
InventoryManager = ManagerUser

HoldWriter = Annotated[
    User,
    Depends(require_roles(RoleName.ADMIN, RoleName.MANAGER, RoleName.SALES_EXECUTIVE)),
]

DiscountRequester = Annotated[
    User,
    Depends(require_roles(RoleName.ADMIN, RoleName.MANAGER, RoleName.SALES_EXECUTIVE)),
]


@router.post("/units", response_model=UnitResponse, status_code=status.HTTP_201_CREATED)
def create_unit_endpoint(
    payload: UnitCreateRequest,
    actor: InventoryManager,
    db: Annotated[Session, Depends(get_db)],
):
    return service.create_unit(db, actor=actor, payload=payload)


@router.post("/units/bulk", response_model=BulkUnitCreateResponse)
def bulk_create_units_endpoint(
    payload: BulkUnitCreateRequest,
    actor: InventoryManager,
    db: Annotated[Session, Depends(get_db)],
    dry_run: Annotated[bool, Query()] = False,
):
    results = service.bulk_create_units(db, actor=actor, rows=payload.rows, dry_run=dry_run)
    return BulkUnitCreateResponse(
        dry_run=dry_run,
        results=results,
        created=sum(result.ok for result in results),
        failed=sum(not result.ok for result in results),
    )


@router.get("/units", response_model=UnitListResponse)
def list_units_endpoint(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
    project_id: UUID | None = None,
    unit_status: Annotated[str | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    rows, total = repository.list_units(
        db,
        tenant_id=current_user.tenant_id,
        offset=(page - 1) * page_size,
        limit=page_size,
        project_id=project_id,
        status=unit_status,
    )
    return UnitListResponse(
        items=rows,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total else 0,
    )


@router.get("/units/{unit_id}", response_model=UnitDetailResponse)
def get_unit_endpoint(
    unit_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    unit = repository.get_unit(db, unit_id, tenant_id=current_user.tenant_id)
    if unit is None:
        raise UnitNotFoundError()
    history = repository.status_history(db, unit_id, tenant_id=current_user.tenant_id)
    response = UnitDetailResponse.model_validate(unit)
    response.status_history = [UnitStatusEventResponse.model_validate(row) for row in history]
    return response


@router.patch("/units/{unit_id}", response_model=UnitResponse)
def update_unit_endpoint(
    unit_id: UUID,
    payload: UnitUpdateRequest,
    actor: InventoryManager,
    db: Annotated[Session, Depends(get_db)],
):
    return service.update_unit(db, actor=actor, unit_id=unit_id, payload=payload)


@router.delete("/units/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unit_endpoint(
    unit_id: UUID,
    actor: InventoryManager,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    service.delete_unit(db, actor=actor, unit_id=unit_id)


@router.patch("/units/{unit_id}/status", response_model=UnitResponse)
def transition_unit_endpoint(
    unit_id: UUID,
    payload: UnitStatusUpdateRequest,
    actor: InventoryManager,
    db: Annotated[Session, Depends(get_db)],
):
    return service.transition_unit(
        db,
        actor=actor,
        unit_id=unit_id,
        to_status=payload.to_status,
        reason=payload.reason,
        source=payload.source,
        approved=payload.approved,
    )


@router.post("/holds", response_model=HoldResponse, status_code=status.HTTP_201_CREATED)
def acquire_hold_endpoint(
    payload: HoldCreateRequest,
    actor: HoldWriter,
    db: Annotated[Session, Depends(get_db)],
):
    return service.acquire_hold(
        db,
        actor=actor,
        unit_id=payload.unit_id,
        lead_id=payload.lead_id,
        opportunity_ref=payload.opportunity_ref,
        hours=payload.hours,
        reason=payload.reason,
    )


@router.post("/holds/{hold_id}/extend", response_model=HoldResponse)
def extend_hold_endpoint(
    hold_id: UUID,
    payload: HoldExtendRequest,
    actor: HoldWriter,
    db: Annotated[Session, Depends(get_db)],
):
    return service.extend_hold(
        db, actor=actor, hold_id=hold_id, hours=payload.hours, reason=payload.reason
    )


@router.post("/holds/{hold_id}/release", response_model=HoldResponse)
def release_hold_endpoint(
    hold_id: UUID,
    payload: HoldReleaseRequest,
    actor: HoldWriter,
    db: Annotated[Session, Depends(get_db)],
):
    return service.release_hold(db, actor=actor, hold_id=hold_id, reason=payload.reason)


@router.post("/holds/{hold_id}/reserve", response_model=UnitResponse)
def reserve_unit_endpoint(
    hold_id: UUID,
    actor: HoldWriter,
    db: Annotated[Session, Depends(get_db)],
):
    return service.reserve_unit(db, actor=actor, hold_id=hold_id)


@router.post("/holds/{hold_id}/convert", response_model=HoldConvertResponse)
def convert_hold_endpoint(
    hold_id: UUID,
    payload: HoldConvertRequest,
    actor: HoldWriter,
    db: Annotated[Session, Depends(get_db)],
):
    hold, booking = service.convert_to_booking(
        db,
        actor=actor,
        hold_id=hold_id,
        consideration_paise=payload.consideration_paise,
        booked_on=payload.booked_on,
    )
    return HoldConvertResponse(hold=hold, booking_id=booking.id)


@router.get("/availability/{project_id}", response_model=AvailabilityResponse)
def availability_endpoint(
    project_id: UUID,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.availability_summary(db, tenant_id=current_user.tenant_id, project_id=project_id)


@router.post(
    "/units/{unit_id}/discount-request",
    response_model=ApprovalRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Propose a discount on a unit (staff only)",
)
def request_unit_discount_endpoint(
    unit_id: UUID,
    payload: DiscountRequestCreateRequest,
    requester: DiscountRequester,
    db: Annotated[Session, Depends(get_db)],
) -> ApprovalRequestResponse:
    """Open a DISCOUNT approval carrying amount_paise and flag the unit PENDING."""

    request = request_unit_discount(
        db,
        actor=requester,
        unit_id=unit_id,
        amount_paise=payload.amount_paise,
        reason=payload.reason,
        approver_id=payload.approver_id,
    )
    return ApprovalRequestResponse.model_validate(request)
