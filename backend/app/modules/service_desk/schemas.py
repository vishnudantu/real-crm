"""API contracts for the service desk."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.service_desk.models import TicketCategory, TicketPriority, TicketStatus


class TicketCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    subject: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=20000)
    category: TicketCategory = TicketCategory.GENERAL
    priority: TicketPriority = TicketPriority.MEDIUM
    contact_id: UUID | None = None
    booking_id: UUID | None = None

    @field_validator("subject", "description", mode="before")
    @classmethod
    def _strip_nonempty(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class TicketAssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assigned_to_id: UUID


class TicketStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: TicketStatus
    resolution_note: str | None = Field(default=None, max_length=20000)


class TicketCommentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    body: str = Field(min_length=1, max_length=4000)
    is_internal: bool = False


class TicketStaffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: str


class TicketCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_id: UUID
    author_id: UUID | None
    body: str
    is_internal: bool
    created_at: datetime


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_number: str
    subject: str
    description: str
    category: TicketCategory
    priority: TicketPriority
    status: TicketStatus
    contact_id: UUID | None
    booking_id: UUID | None
    assigned_to_id: UUID | None
    created_by_id: UUID | None
    sla_due_at: datetime
    first_response_at: datetime | None
    resolved_at: datetime | None
    resolution_note: str | None
    created_at: datetime
    updated_at: datetime


class TicketDetailResponse(TicketResponse):
    comments: list[TicketCommentResponse] = []


class TicketListResponse(BaseModel):
    items: list[TicketResponse]
    total: int
    limit: int
    offset: int
