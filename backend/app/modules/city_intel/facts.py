"""Auto-generate DRAFT ProjectFacts for City Intelligence (Phase 1).

Turns curated locality input into grounded, source-attributed facts that flow
through the existing ProjectFact approve/reject flow (status DRAFT, never
auto-approved), exactly like the solar facts. Three categories:

- "CATCHMENT DEMAND"      — lead/booking aggregation per project locality.
- "LOCATION & AMENITIES"  — curated POI summary + connectivity score.
- "LOCALITY REPORT"       — authored, source-verified research notes.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.projects.models import FactStatus, ProjectFact

CATEGORY_DEMAND = "CATCHMENT DEMAND"
CATEGORY_AMENITIES = "LOCATION & AMENITIES"
CATEGORY_REPORT = "LOCALITY REPORT"


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
    """Create or update a DRAFT fact, staging a pending edit if already approved."""
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

    approved = session.scalar(
        select(ProjectFact).where(
            ProjectFact.tenant_id == tenant_id,
            ProjectFact.project_id == project_id,
            ProjectFact.category == category,
            ProjectFact.status == FactStatus.APPROVED.value,
        )
    )
    if approved is not None:
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


def generate_locality_facts(
    session: Session,
    *,
    tenant_id: UUID,
    project_id: UUID,
    actor_id: UUID,
    demand_answer: str,
    amenities_answer: str | None,
    report_answer: str | None,
) -> list[ProjectFact]:
    """Upsert DRAFT facts for the three Phase-1 categories.

    ``demand_answer`` is always present (computed from leads/bookings).
    ``amenities_answer`` and ``report_answer`` are written only when provided.
    Returns the list of created/updated facts (all DRAFT).
    """
    facts: list[ProjectFact] = [
        _upsert_draft_fact(
            session,
            tenant_id=tenant_id,
            project_id=project_id,
            category=CATEGORY_DEMAND,
            question="What is the buyer demand and conversion for this locality?",
            answer=demand_answer,
            updated_by=actor_id,
        )
    ]
    if amenities_answer:
        facts.append(
            _upsert_draft_fact(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                category=CATEGORY_AMENITIES,
                question="What schools, hospitals, transit and amenities are nearby?",
                answer=amenities_answer,
                updated_by=actor_id,
            )
        )
    if report_answer:
        facts.append(
            _upsert_draft_fact(
                session,
                tenant_id=tenant_id,
                project_id=project_id,
                category=CATEGORY_REPORT,
                question="What source-verified research exists for this locality?",
                answer=report_answer,
                updated_by=actor_id,
            )
        )
    session.commit()
    return facts
