"""Construction milestone business logic: progress, delays, certification.

Status rules
------------
- ``add_progress`` records an append-only :class:`MilestoneUpdate` and derives
  the milestone status: ``IN_PROGRESS`` for 0 < percent < 100, ``COMPLETED``
  at 100 (which also stamps ``actual_date``).
- A milestone that is still unfinished after its ``planned_date`` is flagged
  ``DELAYED`` on the next progress update.
- ``certify_milestone`` (admin only) accepts only ``COMPLETED`` milestones and
  stamps ``CERTIFIED`` plus the certifying user and timestamp.

Demand-letter linkage
---------------------
``CERTIFIED`` is the gate consumers should honour: a demand letter for a
construction-linked installment must only be issuable when the installment's
milestone has ``status == CERTIFIED`` (see
``app.modules.postsales.models.Installment`` for the payment side of that
plan). This module intentionally does NOT auto-issue letters; certification
only records the event. Any future demand-letter integration should query the
certification state here rather than re-deriving it from progress.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.construction import repository
from app.modules.construction.exceptions import (
    MilestoneNotFoundError,
    MilestoneNotCompletedError,
    MilestoneSequenceAlreadyExistsError,
    ProjectNotFoundError,
)
from app.modules.construction.models import (
    ConstructionMilestone,
    MilestoneStatus,
    MilestoneUpdate,
)
from app.modules.projects.models import Project
from app.modules.users.models import RoleName, User


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _get_project(session: Session, project_id: UUID, *, tenant_id: UUID) -> Project:
    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.tenant_id == tenant_id)
    )
    if project is None:
        raise ProjectNotFoundError()
    return project


def _get_milestone(
    session: Session, milestone_id: UUID, *, tenant_id: UUID, for_update: bool = False
) -> ConstructionMilestone:
    milestone = repository.get_milestone(
        session, milestone_id, tenant_id=tenant_id, for_update=for_update
    )
    if milestone is None:
        raise MilestoneNotFoundError()
    return milestone


def _is_admin(session: Session, actor: User) -> bool:
    role = getattr(actor, "role", None)
    if role is not None:
        return getattr(role, "name", None) == RoleName.ADMIN.value
    if getattr(actor, "role_id", None) is None:
        return False
    from app.modules.users.models import Role

    return session.get(Role, actor.role_id).name == RoleName.ADMIN.value


def create_milestone(
    session: Session,
    *,
    actor: User,
    project_id: UUID,
    name: str,
    sequence_no: int,
    planned_date: date,
) -> ConstructionMilestone:
    """Create a NOT_STARTED milestone on a project owned by the actor's tenant."""

    _get_project(session, project_id, tenant_id=actor.tenant_id)
    milestone = ConstructionMilestone(
        tenant_id=actor.tenant_id,
        project_id=project_id,
        name=name,
        sequence_no=sequence_no,
        planned_date=planned_date,
        status=MilestoneStatus.NOT_STARTED.value,
        percent_complete=0,
    )
    session.add(milestone)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise MilestoneSequenceAlreadyExistsError() from exc
    session.refresh(milestone)
    return milestone


def add_progress(
    session: Session,
    *,
    actor: User,
    milestone_id: UUID,
    percent_complete: int,
    note: str,
) -> tuple[ConstructionMilestone, MilestoneUpdate]:
    """Append a progress update and re-derive the milestone's status."""

    milestone = _get_milestone(
        session, milestone_id, tenant_id=actor.tenant_id, for_update=True
    )
    update = MilestoneUpdate(
        tenant_id=actor.tenant_id,
        milestone_id=milestone.id,
        percent_complete=percent_complete,
        note=note,
        author_id=actor.id,
    )
    session.add(update)
    milestone.percent_complete = percent_complete
    if percent_complete >= 100:
        milestone.status = MilestoneStatus.COMPLETED.value
        if milestone.actual_date is None:
            milestone.actual_date = date.today()
    elif date.today() > milestone.planned_date:
        milestone.status = MilestoneStatus.DELAYED.value
    elif percent_complete > 0:
        milestone.status = MilestoneStatus.IN_PROGRESS.value
    session.commit()
    session.refresh(milestone)
    session.refresh(update)
    return milestone, update


def certify_milestone(
    session: Session,
    *,
    actor: User,
    milestone_id: UUID,
    evidence_notes: str | None = None,
) -> ConstructionMilestone:
    """Certify a COMPLETED milestone (admin only).

    Certification is the demand-letter gate described in this module's
    docstring: downstream consumers may issue a construction-linked demand
    letter only once ``status == CERTIFIED``. No letter is issued here.
    """

    if not _is_admin(session, actor):
        from app.modules.users.exceptions import InsufficientPermissionsError

        raise InsufficientPermissionsError()
    milestone = _get_milestone(
        session, milestone_id, tenant_id=actor.tenant_id, for_update=True
    )
    if milestone.status != MilestoneStatus.COMPLETED.value:
        raise MilestoneNotCompletedError()
    milestone.status = MilestoneStatus.CERTIFIED.value
    milestone.certified_by_id = actor.id
    milestone.certified_at = _now_utc()
    if evidence_notes is not None:
        milestone.evidence_notes = evidence_notes
    session.commit()
    session.refresh(milestone)
    return milestone


def list_milestones(
    session: Session, *, tenant_id: UUID, project_id: UUID
) -> list[ConstructionMilestone]:
    """Return the project's milestones ordered by sequence (404 if project is foreign)."""

    _get_project(session, project_id, tenant_id=tenant_id)
    return repository.list_milestones(session, tenant_id=tenant_id, project_id=project_id)


def project_progress_summary(
    session: Session, *, tenant_id: UUID, project_id: UUID
) -> dict[str, object]:
    """Aggregate construction status for one project.

    ``delayed_count`` counts milestones still unfinished after their planned
    date, whether or not a progress update has yet flagged them ``DELAYED``.
    """

    _get_project(session, project_id, tenant_id=tenant_id)
    by_status = repository.count_milestones_by_status(
        session, tenant_id=tenant_id, project_id=project_id
    )
    return {
        "total": sum(by_status.values()),
        "by_status": by_status,
        "avg_percent": repository.average_percent_complete(
            session, tenant_id=tenant_id, project_id=project_id
        ),
        "delayed_count": repository.milestones_past_planned_date(
            session,
            tenant_id=tenant_id,
            project_id=project_id,
            as_of=date.today(),
        ),
    }
