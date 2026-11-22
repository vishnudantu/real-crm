"""Public API contracts for voice intelligence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.voice_intel.models import TranscriptStatus


class TranscriptCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_recording_id: UUID
    language: str = Field(default="en", min_length=1, max_length=8)


class Segment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    start_ms: int = 0
    end_ms: int = 0
    speaker: str = ""
    text: str = ""


class TranscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    call_recording_id: UUID
    call_id: UUID | None
    language: str
    status: TranscriptStatus
    transcript_text: str | None
    segments: list[dict]
    provider: str
    error: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class TranscriptListResponse(BaseModel):
    items: list[TranscriptResponse]
    total: int


class Commitment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str
    needs_review: bool = False


class SummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    transcript_id: UUID
    summary: str
    requirements: dict
    objections: list
    commitments: list[dict]
    next_actions: list
    created_at: datetime
    updated_at: datetime
