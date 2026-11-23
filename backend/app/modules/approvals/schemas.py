"""Public API contracts for approval requests."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.approvals.models import ApprovalStatus


class ApprovalRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_type: str = Field(min_length=1, max_length=48)
    reference_type: str = Field(min_length=1, max_length=48)
    reference_id: UUID
    reason: str = Field(min_length=1, max_length=2000)
    amount_paise: int | None = Field(default=None, ge=0)
    approver_id: UUID | None = None


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: Literal[ApprovalStatus.APPROVED, ApprovalStatus.REJECTED]
    note: str | None = Field(default=None, min_length=1, max_length=2000)


class ApprovalRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_type: str
    reference_type: str
    reference_id: UUID
    requested_by_id: UUID | None
    approver_id: UUID | None
    status: ApprovalStatus
    amount_paise: int | None
    reason: str
    decision_note: str | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApprovalRequestListResponse(BaseModel):
    items: list[ApprovalRequestResponse]
    total: int
    limit: int
    offset: int
