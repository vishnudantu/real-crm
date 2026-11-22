"""Connect dialer endpoints: dispositions, DNC, callbacks, wallboard."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.connect_dialer import service
from app.modules.connect_dialer.schemas import (
    CallbackCreateRequest,
    CallbackResponse,
    DispositionCreateRequest,
    DispositionResponse,
    DoNotCallCreateRequest,
    DoNotCallResponse,
    WallboardResponse,
)
from app.modules.users.models import RoleName, User

router = APIRouter(prefix="/connect", tags=["connect-dialer"])

StaffUser = Annotated[
    User,
    Depends(require_roles(RoleName.ADMIN, RoleName.SALES_EXECUTIVE)),
]


@router.post("/calls/{call_id}/disposition", response_model=DispositionResponse,
             status_code=status.HTTP_201_CREATED)
def record_disposition_endpoint(
    call_id: UUID,
    payload: DispositionCreateRequest,
    actor: StaffUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.record_disposition(
        db, actor=actor, call_id=call_id,
        disposition=payload.disposition, notes=payload.notes,
    )


@router.post("/dnc", response_model=DoNotCallResponse, status_code=status.HTTP_201_CREATED)
def add_dnc_endpoint(
    payload: DoNotCallCreateRequest,
    actor: StaffUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.add_dnc_entry(
        db, actor=actor, phone_number=payload.phone_number, reason=payload.reason
    )


@router.get("/dnc", response_model=list[DoNotCallResponse])
def list_dnc_endpoint(
    actor: StaffUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.list_dnc(db, tenant_id=actor.tenant_id)


@router.delete("/dnc/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_dnc_endpoint(
    entry_id: UUID,
    actor: StaffUser,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    service.remove_dnc_entry(db, actor=actor, entry_id=entry_id)


@router.post("/callbacks", response_model=CallbackResponse, status_code=status.HTTP_201_CREATED)
def schedule_callback_endpoint(
    payload: CallbackCreateRequest,
    actor: StaffUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.schedule_callback(
        db, actor=actor,
        phone_number=payload.phone_number, scheduled_at=payload.scheduled_at,
        lead_id=payload.lead_id, call_id=payload.call_id,
        assigned_to_id=payload.assigned_to_id, notes=payload.notes,
    )


@router.get("/callbacks", response_model=list[CallbackResponse])
def list_callbacks_endpoint(
    actor: StaffUser,
    db: Annotated[Session, Depends(get_db)],
    callback_status: Annotated[str | None, Query(alias="status")] = None,
    only_overdue: bool = False,
):
    return service.list_callbacks(
        db, tenant_id=actor.tenant_id, status_filter=callback_status, only_overdue=only_overdue
    )


@router.post("/callbacks/{callback_id}/complete", response_model=CallbackResponse)
def complete_callback_endpoint(
    callback_id: UUID,
    actor: StaffUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.complete_callback(db, actor=actor, callback_id=callback_id)


@router.get("/wallboard", response_model=WallboardResponse)
def wallboard_endpoint(
    actor: StaffUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.wallboard(db, tenant_id=actor.tenant_id)
