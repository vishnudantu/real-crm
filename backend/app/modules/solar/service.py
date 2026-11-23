"""Solar-facing business logic: sun path computation and unit scoring."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.inventory.models import PropertyUnit
from app.modules.inventory.repository import get_unit
from app.modules.projects.models import Project
from app.modules.projects.repository import get_project_by_id
from app.modules.solar.engine import sun_times
from app.modules.solar.models import TowerOrientation
from app.modules.solar.schemas import (
    SunPathDay,
    SunPathResponse,
    UnitSunScoreResponse,
)
from app.modules.solar.scoring import score_unit_facing
from app.modules.users.models import RoleName, User

__all__ = [
    "update_project_coordinates",
    "upsert_tower_orientation",
    "get_project_sun_path",
    "get_unit_sun_score",
    "TowerOrientationNotFoundError",
    "UnitNotFoundError",
    "ProjectCoordinatesNotSetError",
]


class TowerOrientationNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=404, detail="Tower orientation not found.")


class UnitNotFoundError(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=404, detail="Unit not found.")


class ProjectCoordinatesNotSetError(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=400,
            detail="Project coordinates (latitude/longitude) have not been set.",
        )


def _get_project(session: Session, project_id: UUID, *, tenant_id: UUID) -> Project:
    project = get_project_by_id(session, project_id, tenant_id=tenant_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


def _require_coordinates(project: Project) -> tuple[float, float]:
    lat = getattr(project, "latitude", None)
    lng = getattr(project, "longitude", None)
    if lat is None or lng is None:
        raise ProjectCoordinatesNotSetError()
    return float(lat), float(lng)


def _is_admin(actor: User) -> bool:
    role = getattr(actor, "role", None)
    return role is not None and getattr(role, "name", None) == RoleName.ADMIN.value


def _require_admin(actor: User) -> None:
    if not _is_admin(actor):
        raise HTTPException(status_code=403, detail="Admin access required.")


# ---------------------------------------------------------------------------
# Project coordinates
# ---------------------------------------------------------------------------


def update_project_coordinates(
    session: Session,
    *,
    actor: User,
    project_id: UUID,
    latitude: float,
    longitude: float,
) -> Project:
    """Set latitude/longitude on a project. Admin only."""
    _require_admin(actor)
    project = _get_project(session, project_id, tenant_id=actor.tenant_id)
    project.latitude = latitude
    project.longitude = longitude
    session.commit()
    session.refresh(project)
    return project


# ---------------------------------------------------------------------------
# Tower orientations
# ---------------------------------------------------------------------------


def upsert_tower_orientation(
    session: Session,
    *,
    actor: User,
    project_id: UUID,
    tower_label: str,
    orientation_deg: float,
) -> TowerOrientation:
    """Create or update a tower's facade bearing. Admin only."""
    _require_admin(actor)
    project = _get_project(session, project_id, tenant_id=actor.tenant_id)

    existing = session.scalar(
        select(TowerOrientation).where(
            TowerOrientation.tenant_id == actor.tenant_id,
            TowerOrientation.project_id == project_id,
            TowerOrientation.tower_label == tower_label,
        )
    )
    if existing is not None:
        existing.orientation_deg = orientation_deg
        session.commit()
        session.refresh(existing)
        return existing

    orientation = TowerOrientation(
        tenant_id=actor.tenant_id,
        project_id=project_id,
        tower_label=tower_label,
        orientation_deg=orientation_deg,
    )
    session.add(orientation)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Tower orientation already exists for this project/tower.",
        ) from None
    session.refresh(orientation)
    return orientation


def get_tower_orientation(
    session: Session,
    *,
    tenant_id: UUID,
    project_id: UUID,
    tower_label: str,
) -> TowerOrientation | None:
    """Return a tower orientation if it exists."""
    return session.scalar(
        select(TowerOrientation).where(
            TowerOrientation.tenant_id == tenant_id,
            TowerOrientation.project_id == project_id,
            TowerOrientation.tower_label == tower_label,
        )
    )


# ---------------------------------------------------------------------------
# Sun path
# ---------------------------------------------------------------------------

_REPRESENTATIVE_DATES = [
    (date(2026, 3, 20), "Vernal equinox"),
    (date(2026, 6, 21), "Summer solstice"),
    (date(2026, 9, 22), "Autumnal equinox"),
    (date(2026, 12, 21), "Winter solstice"),
]


def get_project_sun_path(
    session: Session,
    *,
    tenant_id: UUID,
    project_id: UUID,
) -> SunPathResponse:
    """Compute the site's sun path for solstices and equinox."""
    project = _get_project(session, project_id, tenant_id=tenant_id)
    lat, lng = _require_coordinates(project)

    days: list[SunPathDay] = []
    for target_date, _label in _REPRESENTATIVE_DATES:
        st = sun_times(lat, lng, target_date)
        days.append(
            SunPathDay(
                date=target_date.isoformat(),
                sunrise=st.sunrise.isoformat(),
                sunset=st.sunset.isoformat(),
                solar_noon=st.solar_noon.isoformat(),
                day_length_hours=round(st.day_length.total_seconds() / 3600, 2),
            )
        )

    return SunPathResponse(
        project_id=project_id,
        latitude=lat,
        longitude=lng,
        solstices_and_equinox=days,
    )


# ---------------------------------------------------------------------------
# Unit sun score
# ---------------------------------------------------------------------------


def get_unit_sun_score(
    session: Session,
    *,
    tenant_id: UUID,
    unit_id: UUID,
) -> UnitSunScoreResponse:
    """Compute the sun score for a unit.

    Uses the unit's own ``facing_deg`` if set; otherwise falls back to the
    tower's ``orientation_deg``.
    """
    unit = get_unit(session, unit_id, tenant_id=tenant_id)
    if unit is None:
        raise UnitNotFoundError()

    project = _get_project(session, unit.project_id, tenant_id=tenant_id)
    lat, lng = _require_coordinates(project)

    # Determine effective facing bearing.
    facing_deg = getattr(unit, "facing_deg", None)
    if facing_deg is not None:
        bearing = float(facing_deg)
    elif unit.tower:
        tower_orient = get_tower_orientation(
            session,
            tenant_id=tenant_id,
            project_id=unit.project_id,
            tower_label=unit.tower,
        )
        if tower_orient is not None:
            bearing = tower_orient.orientation_deg
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unit has no facing_deg and tower '{unit.tower}' "
                    "has no orientation configured."
                ),
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Unit has no facing_deg and no tower assigned.",
        )

    score = score_unit_facing(bearing, lat, lng)
    return UnitSunScoreResponse(
        unit_id=unit_id,
        facing_bearing=score.facing_bearing,
        facing_label=score.facing_label,
        exposure_class=score.exposure_class,
        comfort_score=score.comfort_score,
        vastu_note=score.vastu_note,
        pricing_premium_min_pct=score.pricing_premium_min_pct,
        pricing_premium_max_pct=score.pricing_premium_max_pct,
        pricing_advisory=score.pricing_advisory,
    )
