"""City Intelligence Engine (Phase 1) — service orchestration.

Fetches tenant-scoped domain data and composes the deterministic analytics in
demand.py and connectivity.py. Curated writes (amenities, locality reports) are
source-attributed and confidence-stamped. DRAFT facts feed the grounded AI
assistant through the existing ProjectFact approve flow.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.city_intel import facts as fact_writer
from app.modules.city_intel.connectivity import connectivity_score, summarize_categories
from app.modules.city_intel.demand import aggregate_demand
from app.modules.city_intel.models import LocalityReport, ProjectAmenity
from app.modules.city_intel.schemas import (
    AmenityCreateRequest,
    LocalityReportCreateRequest,
)
from app.modules.leads.models import Lead
from app.modules.postsales.models import SaleBooking
from app.modules.projects.models import Project
from app.modules.users.models import User


def _get_project(session: Session, project_id: UUID, *, tenant_id: UUID) -> Project:
    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.tenant_id == tenant_id)
    )
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


def demand_by_locality(session: Session, *, tenant_id: UUID) -> list[dict]:
    """Catchment demand per locality (project) across the tenant."""
    projects = list(
        session.scalars(select(Project).where(Project.tenant_id == tenant_id)).all()
    )
    leads = list(session.scalars(select(Lead).where(Lead.tenant_id == tenant_id)).all())
    bookings = list(
        session.scalars(select(SaleBooking).where(SaleBooking.tenant_id == tenant_id)).all()
    )
    rows = aggregate_demand(projects=projects, leads=leads, bookings=bookings)
    return [
        {
            "project_id": r.project_id,
            "locality": r.locality,
            "project_name": r.project_name,
            "lead_count": r.lead_count,
            "booking_count": r.booking_count,
            "conversion_pct": r.conversion_pct,
            "median_budget_paise": r.median_budget_paise,
            "top_price_band": r.top_price_band,
            "top_property_type": r.top_property_type,
        }
        for r in rows
    ]


# ---- Curated POI / connectivity ----


def list_amenities(session: Session, *, tenant_id: UUID, project_id: UUID) -> list[ProjectAmenity]:
    _get_project(session, project_id, tenant_id=tenant_id)
    return list(
        session.scalars(
            select(ProjectAmenity)
            .where(
                ProjectAmenity.tenant_id == tenant_id,
                ProjectAmenity.project_id == project_id,
            )
            .order_by(ProjectAmenity.category, ProjectAmenity.distance_km)
        ).all()
    )


def add_amenity(
    session: Session, *, actor: User, payload: AmenityCreateRequest
) -> ProjectAmenity:
    project = _get_project(session, payload.project_id, tenant_id=actor.tenant_id)
    amenity = ProjectAmenity(
        tenant_id=actor.tenant_id,
        project_id=project.id,
        category=payload.category,
        name=payload.name,
        distance_km=payload.distance_km,
        travel_minutes=payload.travel_minutes,
        source_ref=payload.source_ref,
        confidence=payload.confidence,
        as_of=payload.as_of,
    )
    session.add(amenity)
    session.commit()
    session.refresh(amenity)
    return amenity


def project_connectivity(session: Session, *, tenant_id: UUID, project_id: UUID) -> dict:
    amenities = list_amenities(session, tenant_id=tenant_id, project_id=project_id)
    score = connectivity_score(pois=amenities)
    return {
        "project_id": project_id,
        "score": score.score,
        "by_category": [
            {
                "category": c.category,
                "count": c.count,
                "nearest_km": c.nearest_km,
                "nearest_travel_minutes": c.nearest_travel_minutes,
            }
            for c in score.by_category
        ],
        "notes": score.notes,
    }


# ---- Locality reports ----


def list_reports(session: Session, *, tenant_id: UUID, project_id: UUID) -> list[LocalityReport]:
    _get_project(session, project_id, tenant_id=tenant_id)
    return list(
        session.scalars(
            select(LocalityReport)
            .where(
                LocalityReport.tenant_id == tenant_id,
                LocalityReport.project_id == project_id,
            )
            .order_by(LocalityReport.created_at.desc())
        ).all()
    )


def create_report(
    session: Session, *, actor: User, payload: LocalityReportCreateRequest
) -> LocalityReport:
    project = _get_project(session, payload.project_id, tenant_id=actor.tenant_id)
    report = LocalityReport(
        tenant_id=actor.tenant_id,
        project_id=project.id,
        title=payload.title,
        body=payload.body,
        sources=[s.model_dump(mode="json") for s in payload.sources],
        as_of=payload.as_of,
        status="DRAFT",
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


def _format_demand_answer(session: Session, *, tenant_id: UUID, project: Project) -> str:
    leads = list(
        session.scalars(
            select(Lead).where(Lead.tenant_id == tenant_id, Lead.project_id == project.id)
        ).all()
    )
    bookings = list(
        session.scalars(
            select(SaleBooking).where(
                SaleBooking.tenant_id == tenant_id, SaleBooking.project_id == project.id
            )
        ).all()
    )
    rows = aggregate_demand(projects=[project], leads=leads, bookings=bookings)
    r = rows[0]
    return (
        f"{project.name} ({project.location}): {r.lead_count} leads, "
        f"{r.booking_count} bookings, {r.conversion_pct}% lead→booking conversion. "
        f"Dominant price band: {r.top_price_band}. Dominant property type: {r.top_property_type}."
    )


def _format_amenities_answer(session: Session, *, tenant_id: UUID, project: Project) -> str | None:
    amenities = list_amenities(session, tenant_id=tenant_id, project_id=project.id)
    if not amenities:
        return None
    summaries = summarize_categories(pois=amenities)
    parts = [
        f"{c.count} {c.category}"
        for c in summaries
        if c.count > 0
    ]
    score = connectivity_score(pois=amenities)
    return (
        f"Curated nearby points of interest for {project.name}: " + ", ".join(parts) + ". "
        f"Connectivity score {score.score}/100 (curated data; distances are admin-supplied)."
    )


def _format_report_answer(report: LocalityReport) -> str:
    src = report.sources or []
    if src:
        cited = "; ".join(
            f"{s.get('label')} ({s.get('confidence', 'estimated')})" for s in src
        )
        return f"{report.title}: {report.body} Sources: {cited}."
    return f"{report.title}: {report.body} (No external sources cited.)"


def generate_facts(
    session: Session, *, actor: User, project_id: UUID
) -> list:
    """Generate DRAFT facts for demand, amenities, and any authored reports."""
    project = _get_project(session, project_id, tenant_id=actor.tenant_id)
    demand_answer = _format_demand_answer(session, tenant_id=actor.tenant_id, project=project)
    amenities_answer = _format_amenities_answer(session, tenant_id=actor.tenant_id, project=project)
    reports = list_reports(session, tenant_id=actor.tenant_id, project_id=project.id)
    report_answer = (
        " ".join(_format_report_answer(r) for r in reports) if reports else None
    )
    return fact_writer.generate_locality_facts(
        session,
        tenant_id=actor.tenant_id,
        project_id=project.id,
        actor_id=actor.id,
        demand_answer=demand_answer,
        amenities_answer=amenities_answer,
        report_answer=report_answer,
    )
