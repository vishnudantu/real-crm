"""Construction milestone HTTP endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser, require_roles
from app.modules.construction import service
from app.modules.construction.schemas import (
    CertificationRequest,
    MilestoneCreateRequest,
    MilestoneResponse,
    ProgressCreateRequest,
    ProjectProgressSummary,
)
from app.modules.users.models import RoleName, User

router = APIRouter(prefix="/construction", tags=["construction"])

# Reads are open to all staff; writes stay admin-only.
ConstructionReader = Annotated[
    User,
    Depends(require_roles(RoleName.ADMIN, RoleName.SALES_EXECUTIVE)),
]


@router.post(
    "/milestones",
    response_model=MilestoneResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a construction milestone (admin only)",
)
def create_milestone_endpoint(
    payload: MilestoneCreateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> MilestoneResponse:
    return service.create_milestone(
        db,
        actor=admin,
        project_id=payload.project_id,
        name=payload.name,
        sequence_no=payload.sequence_no,
        planned_date=payload.planned_date,
    )


@router.get(
    "/projects/{project_id}/milestones",
    response_model=list[MilestoneResponse],
    summary="List a project's milestones in sequence order",
)
def list_milestones_endpoint(
    project_id: UUID,
    current_user: ConstructionReader,
    db: Annotated[Session, Depends(get_db)],
) -> list[MilestoneResponse]:
    milestones = service.list_milestones(
        db, tenant_id=current_user.tenant_id, project_id=project_id
    )
    return [MilestoneResponse.model_validate(milestone) for milestone in milestones]


@router.get(
    "/projects/{project_id}/progress",
    response_model=ProjectProgressSummary,
    summary="Aggregate construction progress for a project",
)
def project_progress_endpoint(
    project_id: UUID,
    current_user: ConstructionReader,
    db: Annotated[Session, Depends(get_db)],
) -> ProjectProgressSummary:
    summary = service.project_progress_summary(
        db, tenant_id=current_user.tenant_id, project_id=project_id
    )
    return ProjectProgressSummary.model_validate(summary)


@router.post(
    "/milestones/{milestone_id}/progress",
    response_model=MilestoneResponse,
    summary="Append a progress update to a milestone (admin only)",
)
def add_progress_endpoint(
    milestone_id: UUID,
    payload: ProgressCreateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> MilestoneResponse:
    milestone, _update = service.add_progress(
        db,
        actor=admin,
        milestone_id=milestone_id,
        percent_complete=payload.percent_complete,
        note=payload.note,
    )
    return MilestoneResponse.model_validate(milestone)


@router.post(
    "/milestones/{milestone_id}/certify",
    response_model=MilestoneResponse,
    summary="Certify a completed milestone (admin only)",
)
def certify_milestone_endpoint(
    milestone_id: UUID,
    payload: CertificationRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> MilestoneResponse:
    milestone = service.certify_milestone(
        db,
        actor=admin,
        milestone_id=milestone_id,
        evidence_notes=payload.evidence_notes,
    )
    return MilestoneResponse.model_validate(milestone)
