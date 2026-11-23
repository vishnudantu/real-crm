"""Collections command centre API.

Read endpoints are gated admin + manager + sales executive, matching the
existing post-sales gate style. Promise creation and policy writes are
admin-only (AdminUser). All queries are tenant-scoped; cross-tenant
installment ids resolve to 404.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser, require_roles
from app.modules.collections import service
from app.modules.collections.schemas import (
    CalendarResponse,
    EscalationsResponse,
    PromiseCreateRequest,
    PromiseResponse,
    StatsResponse,
)
from app.modules.users.models import RoleName, User

router = APIRouter(prefix="/collections", tags=["collections"])

CollectionsReader = Annotated[
    User,
    Depends(require_roles(RoleName.ADMIN, RoleName.MANAGER, RoleName.SALES_EXECUTIVE)),
]


@router.get("/calendar", response_model=CalendarResponse)
def calendar_endpoint(
    reader: CollectionsReader,
    db: Annotated[Session, Depends(get_db)],
    month: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")],
    project_id: UUID | None = None,
):
    try:
        return service.calendar(
            db, tenant_id=reader.tenant_id, month=month, project_id=project_id,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post(
    "/installments/{installment_id}/promises",
    response_model=PromiseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_promise_endpoint(
    installment_id: UUID,
    payload: PromiseCreateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    row = service.create_promise(
        db,
        actor=admin,
        installment_id=installment_id,
        amount_paise=payload.amount_paise,
        promised_on=payload.promised_on,
        note=payload.note,
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/installments/{installment_id}/promises", response_model=list[PromiseResponse])
def list_promises_endpoint(
    installment_id: UUID,
    reader: CollectionsReader,
    db: Annotated[Session, Depends(get_db)],
):
    return service.list_promises(
        db, tenant_id=reader.tenant_id, installment_id=installment_id,
    )


@router.get("/escalations", response_model=EscalationsResponse)
def escalations_endpoint(
    reader: CollectionsReader,
    db: Annotated[Session, Depends(get_db)],
    project_id: UUID | None = None,
):
    return service.escalations(db, tenant_id=reader.tenant_id, project_id=project_id)


@router.get("/stats", response_model=StatsResponse)
def stats_endpoint(
    reader: CollectionsReader,
    db: Annotated[Session, Depends(get_db)],
    project_id: UUID | None = None,
):
    return service.stats(db, tenant_id=reader.tenant_id, project_id=project_id)


@router.get("/policy")
def get_policy_endpoint(
    reader: CollectionsReader,
    db: Annotated[Session, Depends(get_db)],
):
    return service.get_policy(db, tenant_id=reader.tenant_id)


@router.put("/policy")
def put_policy_endpoint(
    payload: dict,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    try:
        policy = service.upsert_policy(db, actor=admin, value=payload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    db.commit()
    return policy
