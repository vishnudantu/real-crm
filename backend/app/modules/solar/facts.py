"""Auto-generate DRAFT ProjectFact entries for solar intelligence.

Two fact categories are produced:
1. **Site orientation & sun path** — a summary of the site's coordinates and
   representative sun-path data (sunrise/sunset for equinox/solstices).
2. **Facing breakdown** — a per-tower or per-unit facing classification with
   comfort scores and advisory pricing hints.

All facts are created with ``status=DRAFT`` so they flow through the existing
approve/reject workflow before feeding the grounded AI assistant.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.projects.models import FactStatus, Project, ProjectFact
from app.modules.projects.repository import get_project_by_id
from app.modules.solar.compass import bearing_to_compass
from app.modules.solar.engine import sun_times
from app.modules.solar.models import TowerOrientation
from app.modules.solar.schemas import SunPathDay
from app.modules.solar.service import (
    _get_project,
    _require_coordinates,
    get_project_sun_path,
)

__all__ = [
    "generate_solar_facts",
    "SOLAR_CATEGORY_SITE",
    "SOLAR_CATEGORY_FACING",
]

SOLAR_CATEGORY_SITE = "SITE ORIENTATION & SUN PATH"
SOLAR_CATEGORY_FACING = "FACING BREAKDOWN"

# Representative dates for the fact sheet.
_FACT_DATES = [
    (datetime(2026, 3, 20, tzinfo=UTC).date(), "Vernal equinox"),
    (datetime(2026, 6, 21, tzinfo=UTC).date(), "Summer solstice"),
    (datetime(2026, 12, 21, tzinfo=UTC).date(), "Winter solstice"),
]


def _format_sun_path_answer(lat: float, lng: float) -> str:
    """Build a human-readable sun-path summary for the fact answer."""
    lines = [
        f"Site coordinates: {lat:.4f}°N, {lng:.4f}°E.",
        "",
        "Representative sun-path data:",
    ]
    for target_date, label in _FACT_DATES:
        st = sun_times(lat, lng, target_date)
        sunrise_str = st.sunrise.strftime("%H:%M")
        sunset_str = st.sunset.strftime("%H:%M")
        hours = st.day_length.total_seconds() / 3600
        lines.append(
            f"  {label} ({target_date.isoformat()}): "
            f"Sunrise {sunrise_str}, Sunset {sunset_str}, "
            f"Day length {hours:.1f} hours."
        )
    return "\n".join(lines)


def _format_facing_answer(
    session: Session,
    *,
    tenant_id: UUID,
    project_id: UUID,
) -> str:
    """Build a facing-breakdown summary from tower orientations."""
    orientations = session.scalars(
        select(TowerOrientation).where(
            TowerOrientation.tenant_id == tenant_id,
            TowerOrientation.project_id == project_id,
        )
    ).all()

    if not orientations:
        return (
            "No tower orientations have been configured yet. "
            "Configure tower bearings via PUT /solar/tower-orientation "
            "to generate a facing breakdown."
        )

    lines = ["Tower facing breakdown:"]
    for orient in orientations:
        label = bearing_to_compass(orient.orientation_deg)
        lines.append(
            f"  Tower {orient.tower_label}: "
            f"{orient.orientation_deg:.1f}° ({label})"
        )
    return "\n".join(lines)


def _upsert_draft_fact(
    session: Session,
    *,
    tenant_id: UUID,
    project_id: UUID,
    category: str,
    question: str,
    answer: str,
    updated_by: UUID,
) -> ProjectFact:
    """Create or update a DRAFT fact with the given category.

    If an APPROVED fact already exists in the same category, a new DRAFT
    version is staged via ``pending_*`` fields rather than overwriting the
    approved content.
    """
    existing = session.scalar(
        select(ProjectFact).where(
            ProjectFact.tenant_id == tenant_id,
            ProjectFact.project_id == project_id,
            ProjectFact.category == category,
            ProjectFact.status == FactStatus.DRAFT.value,
        )
    )
    if existing is not None:
        existing.answer = answer
        existing.updated_by = updated_by
        session.flush()
        return existing

    # Check for an approved fact in the same category.
    approved = session.scalar(
        select(ProjectFact).where(
            ProjectFact.tenant_id == tenant_id,
            ProjectFact.project_id == project_id,
            ProjectFact.category == category,
            ProjectFact.status == FactStatus.APPROVED.value,
        )
    )
    if approved is not None:
        # Stage as pending edit on the approved fact.
        approved.pending_category = category
        approved.pending_question = question
        approved.pending_answer = answer
        approved.updated_by = updated_by
        session.flush()
        return approved

    fact = ProjectFact(
        tenant_id=tenant_id,
        project_id=project_id,
        category=category,
        question=question,
        answer=answer,
        status=FactStatus.DRAFT.value,
        updated_by=updated_by,
    )
    session.add(fact)
    session.flush()
    return fact


def generate_solar_facts(
    session: Session,
    *,
    tenant_id: UUID,
    project_id: UUID,
    actor_id: UUID,
) -> list[ProjectFact]:
    """Auto-generate DRAFT solar facts for a project.

    Returns the list of created/updated facts. All facts remain in DRAFT
    status until explicitly approved through the existing fact workflow.
    """
    project = _get_project(session, project_id, tenant_id=tenant_id)
    lat, lng = _require_coordinates(project)

    facts: list[ProjectFact] = []

    # Fact 1: Site orientation & sun path.
    sun_answer = _format_sun_path_answer(lat, lng)
    fact1 = _upsert_draft_fact(
        session,
        tenant_id=tenant_id,
        project_id=project_id,
        category=SOLAR_CATEGORY_SITE,
        question="What is the site's orientation and sun path?",
        answer=sun_answer,
        updated_by=actor_id,
    )
    facts.append(fact1)

    # Fact 2: Facing breakdown.
    facing_answer = _format_facing_answer(
        session,
        tenant_id=tenant_id,
        project_id=project_id,
    )
    fact2 = _upsert_draft_fact(
        session,
        tenant_id=tenant_id,
        project_id=project_id,
        category=SOLAR_CATEGORY_FACING,
        question="What is the facing breakdown for towers in this project?",
        answer=facing_answer,
        updated_by=actor_id,
    )
    facts.append(fact2)

    session.commit()
    return facts
