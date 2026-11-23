"""Advanced Inventory Intelligence (Module 20) — service orchestration.

Fetches tenant-scoped domain data and delegates the deterministic heuristics to
pure functions in this package (revenue_map, hold_expiry, unsold_risk,
conflict_detection, recommendations). No pricing model is required for these
sub-features; booked values come from existing SaleBooking.consideration_paise.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.inventory.intelligence.conflict_detection import detect_unit_conflicts
from app.modules.inventory.intelligence.hold_expiry import assess_hold_expiry
from app.modules.inventory.intelligence.recommendations import recommend_alternatives
from app.modules.inventory.intelligence.revenue_map import build_revenue_map
from app.modules.inventory.intelligence.schemas import (
    ConflictResponse,
    HoldExpiryResponse,
    RecommendationResponse,
    RevenueMapResponse,
    UnitConflict,
    UnitRecommendation,
    UnsoldRiskResponse,
)
from app.modules.inventory.intelligence.unsold_risk import predict_unsold_risk
from app.modules.inventory.models import HoldState, PropertyUnit, UnitHold, UnitStatus
from app.modules.postsales.models import SaleBooking


def _units_for_project(
    session: Session, *, tenant_id: UUID, project_id: UUID
) -> list[PropertyUnit]:
    return list(
        session.scalars(
            select(PropertyUnit).where(
                PropertyUnit.tenant_id == tenant_id,
                PropertyUnit.project_id == project_id,
            )
        ).all()
    )


def _require_project_units(
    session: Session, *, tenant_id: UUID, project_id: UUID
) -> list[PropertyUnit]:
    units = _units_for_project(session, tenant_id=tenant_id, project_id=project_id)
    if not units:
        # Could be a foreign project (404) or a real project with no inventory.
        # Distinguish by checking the project row itself for a clean 404.
        from app.modules.projects.models import Project

        project = session.scalar(
            select(Project).where(
                Project.id == project_id, Project.tenant_id == tenant_id
            )
        )
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found."
            )
    return units


def _booked_values(
    session: Session, *, tenant_id: UUID, project_id: UUID
) -> dict[str, int]:
    rows = session.execute(
        select(SaleBooking.unit_id, SaleBooking.consideration_paise).where(
            SaleBooking.tenant_id == tenant_id,
            SaleBooking.unit_id.is_not(None),
        )
    ).all()
    # Restrict to this project's units via the join-free path: the caller
    # intersects with project unit ids. Values keyed by unit_id as str.
    return {str(unit_id): int(value) for unit_id, value in rows if unit_id is not None}


def revenue_map(
    session: Session, *, tenant_id: UUID, project_id: UUID, today: date | None = None
) -> RevenueMapResponse:
    units = _require_project_units(session, tenant_id=tenant_id, project_id=project_id)
    booked = _booked_values(session, tenant_id=tenant_id, project_id=project_id)
    result = build_revenue_map(
        units=units, booked_values=booked, today=today or date.today()
    )
    return RevenueMapResponse(
        total_units=result.total_units,
        by_status=result.by_status,
        total_booked_value_paise=result.total_booked_value_paise,
        avg_unit_age_days=result.avg_unit_age_days,
        oldest_unit_age_days=result.oldest_unit_age_days,
        rows=[
            {
                "unit_id": str(r.unit_id),
                "internal_code": r.internal_code,
                "status": r.status,
                "booked_value_paise": r.booked_value_paise,
                "age_days": r.age_days,
            }
            for r in result.rows
        ],
    )


def hold_expiry(
    session: Session, *, tenant_id: UUID, project_id: UUID, now: datetime | None = None
) -> HoldExpiryResponse:
    units = _require_project_units(session, tenant_id=tenant_id, project_id=project_id)
    unit_ids = [u.id for u in units]
    holds = list(
        session.scalars(
            select(UnitHold).where(
                UnitHold.tenant_id == tenant_id,
                UnitHold.unit_id.in_(unit_ids) if unit_ids else False,
                UnitHold.state == HoldState.ACTIVE.value,
            )
        ).all()
    ) if unit_ids else []
    risks = assess_hold_expiry(holds=holds, now=now or datetime.now(UTC))
    return HoldExpiryResponse(
        items=[
            {
                "hold_id": str(r.hold_id),
                "unit_id": str(r.unit_id),
                "expires_at": r.expires_at,
                "hours_remaining": r.hours_remaining,
                "extension_count": r.extension_count,
                "risk": r.risk,
            }
            for r in risks
        ],
        total=len(risks),
    )


def unsold_risk(
    session: Session,
    *,
    tenant_id: UUID,
    project_id: UUID,
    today: date | None = None,
    medium_days: int = 60,
    high_days: int = 120,
) -> UnsoldRiskResponse:
    units = _require_project_units(session, tenant_id=tenant_id, project_id=project_id)
    risks = predict_unsold_risk(
        units=units, today=today or date.today(), medium_days=medium_days, high_days=high_days
    )
    return UnsoldRiskResponse(
        items=[
            {
                "unit_id": str(r.unit_id),
                "internal_code": r.internal_code,
                "status": r.status,
                "days_available": r.days_available,
                "risk": r.risk,
            }
            for r in risks
        ],
        total=len(risks),
        medium_days=medium_days,
        high_days=high_days,
    )


def conflicts(
    session: Session, *, tenant_id: UUID, project_id: UUID
) -> ConflictResponse:
    units = _require_project_units(session, tenant_id=tenant_id, project_id=project_id)
    unit_ids = [u.id for u in units]
    active_holds = list(
        session.scalars(
            select(UnitHold).where(
                UnitHold.tenant_id == tenant_id,
                UnitHold.unit_id.in_(unit_ids) if unit_ids else False,
                UnitHold.state == HoldState.ACTIVE.value,
            )
        ).all()
    ) if unit_ids else []
    sold_ids = {str(u.id) for u in units if u.status == UnitStatus.SOLD.value}
    booked_ids = {str(u.id) for u in units if u.status == UnitStatus.BOOKED.value}
    found = detect_unit_conflicts(
        units=units,
        active_holds=active_holds,
        sold_unit_ids=sold_ids,
        booked_unit_ids=booked_ids,
    )
    return ConflictResponse(
        items=[
            UnitConflict(unit_id=str(c.unit_id), code=c.code, kind=c.kind, detail=c.detail)
            for c in found
        ],
        total=len(found),
    )


def recommendations(
    session: Session, *, tenant_id: UUID, unit_id: UUID, limit: int = 5
) -> RecommendationResponse:
    requested = session.scalar(
        select(PropertyUnit).where(
            PropertyUnit.id == unit_id, PropertyUnit.tenant_id == tenant_id
        )
    )
    if requested is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found."
        )
    candidates = _units_for_project(
        session, tenant_id=tenant_id, project_id=requested.project_id
    )
    recs = recommend_alternatives(requested=requested, candidates=candidates, limit=limit)
    return RecommendationResponse(
        requested_unit_id=str(unit_id),
        items=[
            UnitRecommendation(
                unit_id=str(r.unit_id),
                internal_code=r.internal_code,
                score=r.score,
                reasons=r.reasons,
            )
            for r in recs
        ],
        total=len(recs),
    )
