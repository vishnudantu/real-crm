"""Pydantic contracts for the connect dialer."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.connect_dialer.models import CallbackStatus, Disposition


class DispositionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    disposition: Disposition
    notes: str | None = Field(default=None, max_length=2000)


class DispositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    call_id: UUID
    disposition: Disposition
    notes: str | None = None
    recorded_by_id: UUID | None = None
    created_at: datetime


class DoNotCallCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    phone_number: str = Field(min_length=7, max_length=32)
    reason: str | None = Field(default=None, max_length=500)


class DoNotCallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    phone_number: str
    reason: str | None = None
    added_by_id: UUID | None = None
    created_at: datetime


class CallbackCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    phone_number: str = Field(min_length=7, max_length=32)
    scheduled_at: datetime
    lead_id: UUID | None = None
    call_id: UUID | None = None
    assigned_to_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CallbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID | None = None
    call_id: UUID | None = None
    phone_number: str
    assigned_to_id: UUID | None = None
    scheduled_at: datetime
    status: CallbackStatus
    notes: str | None = None
    created_at: datetime


class WallboardResponse(BaseModel):
    active_calls: int
    ringing_calls: int
    waiting_callbacks: int
    overdue_callbacks: int
    completed_today: int
    available_agents: int
    busy_agents: int
