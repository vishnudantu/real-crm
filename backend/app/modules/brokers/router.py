"""Broker/channel-partner registry API and performance rollup.

ADMIN owns writes; ADMIN and SALES_EXECUTIVE may read the registry and
performance. Every lookup is tenant-scoped, so cross-tenant ids return 404.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser, require_roles
from app.modules.brokers import service
from app.modules.brokers.models import BrokerStatus
from app.modules.brokers.schemas import (
    BrokerCreateRequest,
    BrokerListResponse,
    BrokerPerformanceResponse,
    BrokerResponse,
    BrokerUpdateRequest,
)
from app.modules.users.models import RoleName, User

router = APIRouter(prefix="/brokers", tags=["brokers"])

BrokerStaffUser = Annotated[
    User,
    Depends(require_roles(RoleName.ADMIN, RoleName.SALES_EXECUTIVE)),
]


@router.post("", response_model=BrokerResponse, status_code=status.HTTP_201_CREATED)
def register_broker_endpoint(
    payload: BrokerCreateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.register_broker(db, actor=admin, **payload.model_dump())


@router.get("", response_model=BrokerListResponse)
def list_brokers_endpoint(
    staff: BrokerStaffUser,
    db: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[BrokerStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(max_length=255)] = None,
):
    rows = service.list_brokers(
        db,
        tenant_id=staff.tenant_id,
        status=status_filter.value if status_filter else None,
        search=search,
    )
    return BrokerListResponse(items=rows, total=len(rows))


@router.get("/{broker_id}", response_model=BrokerResponse)
def get_broker_endpoint(
    broker_id: UUID,
    staff: BrokerStaffUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.get_broker(db, broker_id, tenant_id=staff.tenant_id)


@router.patch("/{broker_id}", response_model=BrokerResponse)
def update_broker_endpoint(
    broker_id: UUID,
    payload: BrokerUpdateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    fields = payload.model_dump(exclude_unset=True)
    if "status" in fields and fields["status"] is not None:
        fields["status"] = fields["status"].value
    return service.update_broker(db, actor=admin, broker_id=broker_id, fields=fields)


@router.get("/{broker_id}/performance", response_model=BrokerPerformanceResponse)
def broker_performance_endpoint(
    broker_id: UUID,
    staff: BrokerStaffUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.broker_performance(db, actor=staff, broker_id=broker_id)
