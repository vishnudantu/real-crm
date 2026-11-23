"""Voice intelligence API: enqueue/process transcriptions and read transcripts/summaries.

Admin writes (enqueue, process); admin or sales-exec reads. All queries are
tenant-scoped; cross-tenant access returns 404.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser, require_roles
from app.modules.users.models import RoleName, User
from app.modules.voice_intel import service
from app.modules.voice_intel.providers import TranscriptionProvider
from app.modules.voice_intel.schemas import (
    SummaryResponse,
    TranscriptCreateRequest,
    TranscriptListResponse,
    TranscriptResponse,
)

router = APIRouter(prefix="/voice-intel", tags=["voice-intel"])

StaffUser = Annotated[
    User,
    Depends(require_roles(RoleName.ADMIN, RoleName.SALES_EXECUTIVE)),
]


def get_transcription_provider() -> TranscriptionProvider:
    """Injectable provider seam (overridable in tests)."""
    return service.get_default_provider()


@router.post(
    "/transcriptions",
    response_model=TranscriptResponse,
    status_code=status.HTTP_201_CREATED,
)
def enqueue_transcription_endpoint(
    payload: TranscriptCreateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.enqueue_transcription(
        db,
        tenant_id=admin.tenant_id,
        call_recording_id=payload.call_recording_id,
        language=payload.language,
    )


@router.post("/transcriptions/{transcript_id}/process", response_model=TranscriptResponse)
def process_transcription_endpoint(
    transcript_id: UUID,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    provider: Annotated[TranscriptionProvider, Depends(get_transcription_provider)],
):
    return service.process_transcript(
        db, transcript_id, tenant_id=admin.tenant_id, provider=provider
    )


@router.get("/transcriptions", response_model=TranscriptListResponse)
def list_transcriptions_endpoint(
    staff: StaffUser,
    db: Annotated[Session, Depends(get_db)],
    transcript_status: Annotated[str | None, Query(alias="status")] = None,
):
    rows = service.list_transcripts(db, tenant_id=staff.tenant_id, status=transcript_status)
    return TranscriptListResponse(items=rows, total=len(rows))


@router.get("/transcriptions/{transcript_id}", response_model=TranscriptResponse)
def get_transcription_endpoint(
    transcript_id: UUID,
    staff: StaffUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.require_transcript(db, transcript_id, tenant_id=staff.tenant_id)


@router.get("/transcriptions/{transcript_id}/summary", response_model=SummaryResponse)
def get_summary_endpoint(
    transcript_id: UUID,
    staff: StaffUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.get_summary(db, transcript_id, tenant_id=staff.tenant_id)
