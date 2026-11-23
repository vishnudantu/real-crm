"""Advanced Inventory Intelligence (Module 20) — HTTP endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.inventory.intelligence import service
from app.modules.inventory.intelligence.schemas import (
    ConflictResponse,
    HoldExpiryResponse,
    RecommendationResponse,
    RevenueMapResponse,
    UnsoldRiskResponse,
)
from app.modules.users.models import RoleName, User

router = APIRouter(prefix="/inventory/intelligence", tags=["inventory-intelligence"])

IntelligenceReader = Annotated[
    User,
    Depends(require_roles(RoleName.ADMIN, RoleName.SALES_EXECUTIVE)),
]


@router.get(
    "/projects/{project_id}/revenue-map",
    response_model=RevenueMapResponse,
    summary="Inventory revenue map: value, status and aging",
)
def revenue_map_endpoint(
    project_id: UUID,
    current_user: IntelligenceReader,
    db: Annotated[Session, Depends(get_db)],
) -> RevenueMapResponse:
    return service.revenue_map(
        db, tenant_id=current_user.tenant_id, project_id=project_id
    )


@router.get(
    "/projects/{project_id}/hold-expiry",
    response_model=HoldExpiryResponse,
    summary="Holds likely to expire without conversion",
)
def hold_expiry_endpoint(
    project_id: UUID,
    current_user: IntelligenceReader,
    db: Annotated[Session, Depends(get_db)],
) -> HoldExpiryResponse:
    return service.hold_expiry(
        db, tenant_id=current_user.tenant_id, project_id=project_id
    )


@router.get(
    "/projects/{project_id}/unsold-risk",
    response_model=UnsoldRiskResponse,
    summary="Predict units at risk of prolonged selling",
)
def unsold_risk_endpoint(
    project_id: UUID,
    current_user: IntelligenceReader,
    db: Annotated[Session, Depends(get_db)],
    medium_days: Annotated[int, Query(gt=0)] = 60,
    high_days: Annotated[int, Query(gt=0)] = 120,
) -> UnsoldRiskResponse:
    return service.unsold_risk(
        db,
        tenant_id=current_user.tenant_id,
        project_id=project_id,
        medium_days=medium_days,
        high_days=high_days,
    )


@router.get(
    "/projects/{project_id}/conflicts",
    response_model=ConflictResponse,
    summary="Detect inconsistent booking/reservation/sale states",
)
def conflicts_endpoint(
    project_id: UUID,
    current_user: IntelligenceReader,
    db: Annotated[Session, Depends(get_db)],
) -> ConflictResponse:
    return service.conflicts(db, tenant_id=current_user.tenant_id, project_id=project_id)


@router.get(
    "/units/{unit_id}/recommendations",
    response_model=RecommendationResponse,
    summary="Recommend available alternative units",
)
def recommendations_endpoint(
    unit_id: UUID,
    current_user: IntelligenceReader,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> RecommendationResponse:
    return service.recommendations(
        db, tenant_id=current_user.tenant_id, unit_id=unit_id, limit=limit
    )
