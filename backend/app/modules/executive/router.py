"""Executive cockpit API: admin-only, read-only aggregation endpoints."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser
import app.modules.executive.briefing as briefing_service
from app.modules.executive import service
from app.modules.executive.schemas import BriefingResponse, CockpitResponse

router = APIRouter(prefix="/executive", tags=["Executive Cockpit"])


@router.get(
    "/cockpit",
    response_model=CockpitResponse,
    summary="Executive cockpit aggregation (Admin only)",
    description=(
        "Sales velocity, live-receipt collections, inventory and unsold value, "
        "pending approvals, overdue installments, SLA-breaching tickets, and a "
        "velocity ranking of projects. Read-only over existing tables; voided "
        "receipts are excluded from every money total."
    ),
)
def get_cockpit(
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    project_id: Annotated[UUID | None, Query()] = None,
    months: Annotated[int, Query(ge=1, le=24)] = 12,
) -> CockpitResponse:
    payload = service.cockpit(
        db, tenant_id=admin.tenant_id, project_id=project_id, months=months
    )
    return CockpitResponse.model_validate(payload)


@router.get(
    "/briefing",
    response_model=BriefingResponse,
    summary="Morning briefing (Admin only)",
    description=(
        "Deterministic factual digest for one UTC day (default: yesterday): "
        "leads, visits, bookings, receipts, tickets, approval decisions, and "
        "open items. Rendered from SQL counts with fixed templates — no AI/LLM "
        "call — so re-requesting the same date over unchanged data returns the "
        "same lines."
    ),
)
def get_briefing(
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    date_: Annotated[
        date | None, Query(alias="date", description="UTC day to summarise; defaults to yesterday")
    ] = None,
) -> BriefingResponse:
    payload = briefing_service.briefing(db, tenant_id=admin.tenant_id, briefing_date=date_)
    return BriefingResponse.model_validate(payload)
