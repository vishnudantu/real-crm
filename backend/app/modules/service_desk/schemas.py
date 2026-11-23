"""API contracts for the service desk."""

from __future__ import annotations

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.service_desk.models import (
    KbArticleStatus,
    TicketCategory,
    TicketPriority,
    TicketStatus,
)


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


class TicketSatisfactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_id: UUID
    rating: int | None
    feedback: str | None
    created_at: datetime
    responded_at: datetime | None


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
    closed_at: datetime | None
    resolution_note: str | None
    created_at: datetime
    updated_at: datetime


class TicketDetailResponse(TicketResponse):
    comments: list[TicketCommentResponse] = []
    satisfaction: TicketSatisfactionResponse | None = None


class TicketListResponse(BaseModel):
    items: list[TicketResponse]
    total: int
    limit: int
    offset: int


# --------------------------------------------------------------------------- #
# Knowledge base
# --------------------------------------------------------------------------- #


class KbArticleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=80)
    body_markdown: str = Field(min_length=1, max_length=100000)
    category: str = Field(min_length=1, max_length=64)

    @field_validator("title", "body_markdown", "category", "slug", mode="before")
    @classmethod
    def _strip_nonempty(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("slug")
    @classmethod
    def _slug_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
            raise ValueError(
                "slug must be lowercase letters, digits and single hyphens."
            )
        return value


class KbArticleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=255)
    body_markdown: str | None = Field(default=None, min_length=1, max_length=100000)
    category: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("title", "body_markdown", "category", mode="before")
    @classmethod
    def _strip_nonempty(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class KbArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    slug: str
    body_markdown: str
    category: str
    status: KbArticleStatus
    published_at: datetime | None
    author_id: UUID | None
    created_at: datetime
    updated_at: datetime


class KbArticleListResponse(BaseModel):
    items: list[KbArticleResponse]
    total: int
    limit: int
    offset: int


# --------------------------------------------------------------------------- #
# CSAT (satisfaction survey)
# --------------------------------------------------------------------------- #


class SatisfactionSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rating: int = Field(ge=1, le=5)
    feedback: str | None = Field(default=None, max_length=2000)

    @field_validator("feedback", mode="before")
    @classmethod
    def _strip_feedback(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class CsatPeriodStat(BaseModel):
    period: str
    surveys: int
    rated: int
    average_rating: float | None


class OpenTicketTrendPoint(BaseModel):
    period: str
    opened: int
    closed: int


class CsatStatsResponse(BaseModel):
    period: str
    surveys: int
    rated: int
    average_rating: float | None
    response_rate: float | None
    rating_histogram: dict[int, int]
    unresolved_tickets: int
    periods: list[CsatPeriodStat]
    ticket_trends: list[OpenTicketTrendPoint]


class AgentSuggestionResponse(BaseModel):
    article_id: UUID
    title: str
    slug: str
    category: str
    score: int
