"""Database access for construction milestones and progress updates."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.modules.construction.models import ConstructionMilestone, MilestoneStatus, MilestoneUpdate


def _locked(session: Session, statement: Select[object]) -> Select[object]:
    """Apply a row lock on databases that support it.

    SQLite is used by the isolated test suite and does not support
    ``FOR UPDATE``; PostgreSQL is used in production and does.
    """

    if session.get_bind().dialect.name != "sqlite":
        return statement.with_for_update()
    return statement


def get_milestone(
    session: Session,
    milestone_id: UUID,
    *,
    tenant_id: UUID,
    for_update: bool = False,
) -> ConstructionMilestone | None:
    """Return one milestone by ID within the requested tenant."""

    statement = select(ConstructionMilestone).where(
        ConstructionMilestone.id == milestone_id,
        ConstructionMilestone.tenant_id == tenant_id,
    )
    if for_update:
        statement = _locked(session, statement)
    return session.scalar(statement)


def list_milestones(
    session: Session,
    *,
    tenant_id: UUID,
    project_id: UUID,
) -> list[ConstructionMilestone]:
    """Return the project's milestones ordered by their planned sequence."""

    return list(
        session.scalars(
            select(ConstructionMilestone)
            .where(
                ConstructionMilestone.tenant_id == tenant_id,
                ConstructionMilestone.project_id == project_id,
            )
            .order_by(ConstructionMilestone.sequence_no, ConstructionMilestone.created_at)
        ).all()
    )


def count_milestones_by_status(
    session: Session, *, tenant_id: UUID, project_id: UUID
) -> dict[str, int]:
    """Return the per-status milestone counts for one project."""

    rows = session.execute(
        select(ConstructionMilestone.status, func.count())
        .where(
            ConstructionMilestone.tenant_id == tenant_id,
            ConstructionMilestone.project_id == project_id,
        )
        .group_by(ConstructionMilestone.status)
    ).all()
    return {status: count for status, count in rows}


def average_percent_complete(
    session: Session, *, tenant_id: UUID, project_id: UUID
) -> float:
    """Return the mean completion percentage, or 0.0 for a project with none."""

    avg = session.scalar(
        select(func.avg(ConstructionMilestone.percent_complete)).where(
            ConstructionMilestone.tenant_id == tenant_id,
            ConstructionMilestone.project_id == project_id,
        )
    )
    return float(avg) if avg is not None else 0.0


def list_updates(
    session: Session,
    *,
    tenant_id: UUID,
    milestone_id: UUID,
) -> list[MilestoneUpdate]:
    """Return a milestone's progress log oldest-first."""

    return list(
        session.scalars(
            select(MilestoneUpdate)
            .where(
                MilestoneUpdate.tenant_id == tenant_id,
                MilestoneUpdate.milestone_id == milestone_id,
            )
            .order_by(MilestoneUpdate.created_at, MilestoneUpdate.id)
        ).all()
    )


def milestones_past_planned_date(
    session: Session, *, tenant_id: UUID, project_id: UUID, as_of: date
) -> int:
    """Count unfinished milestones whose planned date has already passed."""

    unfinished = (
        MilestoneStatus.NOT_STARTED.value,
        MilestoneStatus.IN_PROGRESS.value,
        MilestoneStatus.DELAYED.value,
    )
    return (
        session.scalar(
            select(func.count())
            .select_from(ConstructionMilestone)
            .where(
                ConstructionMilestone.tenant_id == tenant_id,
                ConstructionMilestone.project_id == project_id,
                ConstructionMilestone.planned_date < as_of,
                ConstructionMilestone.status.in_(unfinished),
            )
        )
        or 0
    )
