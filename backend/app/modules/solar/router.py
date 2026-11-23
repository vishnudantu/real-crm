"""Solar-facing HTTP endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser, require_roles
from app.modules.solar import service
from app.modules.solar.facts import generate_solar_facts
from app.modules.solar.schemas import (
    ProjectCoordinatesUpdate,
    SunPathResponse,
    TowerOrientationResponse,
    TowerOrientationUpsert,
    UnitSunScoreResponse,
)
from app.modules.users.models import RoleName, User

router = APIRouter(prefix="/solar", tags=["solar"])

SolarReader = Annotated[
    User,
    Depends(require_roles(RoleName.ADMIN, RoleName.SALES_EXECUTIVE)),
]


@router.patch(
    "/projects/{project_id}/coordinates",
    response_model=dict,
    summary="Set project site coordinates (admin only)",
)
def update_coordinates_endpoint(
    project_id: UUID,
    payload: ProjectCoordinatesUpdate,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Set the site's latitude and longitude on a project."""
    project = service.update_project_coordinates(
        db,
        actor=admin,
        project_id=project_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    return {
        "project_id": str(project.id),
        "latitude": project.latitude,
        "longitude": project.longitude,
    }


@router.put(
    "/tower-orientation",
    response_model=TowerOrientationResponse,
    summary="Create or update a tower orientation (admin only)",
)
def upsert_tower_orientation_endpoint(
    payload: TowerOrientationUpsert,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> TowerOrientationResponse:
    """Create or update a tower's facade bearing."""
    orientation = service.upsert_tower_orientation(
        db,
        actor=admin,
        project_id=payload.project_id,
        tower_label=payload.tower_label,
        orientation_deg=payload.orientation_deg,
    )
    return TowerOrientationResponse.model_validate(orientation)


@router.get(
    "/projects/{project_id}/sun-path",
    response_model=SunPathResponse,
    summary="Get project sun path for solstices and equinox",
)
def get_sun_path_endpoint(
    project_id: UUID,
    current_user: SolarReader,
    db: Annotated[Session, Depends(get_db)],
) -> SunPathResponse:
    """Return sunrise/sunset/solar-noon for representative dates."""
    return service.get_project_sun_path(
        db,
        tenant_id=current_user.tenant_id,
        project_id=project_id,
    )


@router.get(
    "/units/{unit_id}/sun-score",
    response_model=UnitSunScoreResponse,
    summary="Get unit sun-exposure score",
)
def get_unit_sun_score_endpoint(
    unit_id: UUID,
    current_user: SolarReader,
    db: Annotated[Session, Depends(get_db)],
) -> UnitSunScoreResponse:
    """Return comfort score, Vastu note, and pricing hint for a unit."""
    return service.get_unit_sun_score(
        db,
        tenant_id=current_user.tenant_id,
        unit_id=unit_id,
    )


@router.post(
    "/projects/{project_id}/generate-facts",
    response_model=dict,
    summary="Auto-generate DRAFT solar facts (admin only)",
)
def generate_facts_endpoint(
    project_id: UUID,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Auto-generate DRAFT ProjectFact entries for solar intelligence."""
    facts = generate_solar_facts(
        db,
        tenant_id=admin.tenant_id,
        project_id=project_id,
        actor_id=admin.id,
    )
    return {
        "generated": len(facts),
        "fact_ids": [str(f.id) for f in facts],
        "status": "DRAFT",
    }
