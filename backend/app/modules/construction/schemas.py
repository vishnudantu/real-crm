"""Pydantic contracts for construction milestone tracking."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.construction.models import MilestoneStatus


class MilestoneCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: UUID
    name: str = Field(min_length=1, max_length=255)
    sequence_no: int = Field(ge=1)
    planned_date: date


class ProgressCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    percent_complete: int = Field(ge=0, le=100)
    note: str = Field(min_length=1, max_length=5000)


class CertificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    evidence_notes: str | None = Field(default=None, max_length=10000)


class MilestoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    sequence_no: int
    planned_date: date
    actual_date: date | None
    status: MilestoneStatus
    percent_complete: int
    evidence_notes: str | None
    certified_by_id: UUID | None
    certified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    milestone_id: UUID
    percent_complete: int
    note: str
    author_id: UUID | None
    created_at: datetime


class ProjectProgressSummary(BaseModel):
    total: int
    by_status: dict[str, int]
    avg_percent: float
    delayed_count: int
