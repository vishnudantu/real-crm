"""Pydantic schemas for the customers module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.modules.customers.models import (
    ContactMethodKind,
    ContactStatus,
    OpportunityStage,
    VerificationState,
)
from app.modules.leads.schemas import normalize_email, normalize_phone

_BUDGET_MAX = 10**12


class ContactSearchRequest(BaseModel):
    """Resolve preview: at least one of email/phone required."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    display_name: str | None = Field(default=None, max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: object) -> object:
        return normalize_email(value)

    @field_validator("phone", mode="before")
    @classmethod
    def _normalize_phone(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return normalize_phone(stripped) if stripped else None
        return value

    @model_validator(mode="after")
    def _require_contact(self) -> ContactSearchRequest:
        if self.email is None and self.phone is None:
            raise ValueError("Provide at least one of email or phone.")
        return self


class ContactMethodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: ContactMethodKind
    value: str
    normalized_value: str
    verification_state: VerificationState
    provenance: dict
    is_primary: bool
    last_seen_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    canonical_key: str
    display_name: str
    primary_language: str
    status: ContactStatus
    notes: str | None = None
    merged_into_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ContactDetailResponse(ContactResponse):
    methods: list[ContactMethodResponse] = []


class ContactResolvePreviewResponse(BaseModel):
    """Result of POST /customers/search."""

    exists: bool
    would_create: bool
    contact: ContactResponse | None = None
    matched_method: ContactMethodResponse | None = None
    normalized_email: str | None = None
    normalized_phone: str | None = None


class ContactListResponse(BaseModel):
    items: list[ContactResponse]
    total: int
    page: int
    page_size: int
    pages: int


class OpportunityCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_id: UUID
    from_lead_id: UUID | None = None
    owner_user_id: UUID | None = None
    budget_min: int | None = Field(default=None, ge=0, le=_BUDGET_MAX)
    budget_max: int | None = Field(default=None, ge=0, le=_BUDGET_MAX)
    preferred_configuration: str | None = Field(default=None, max_length=100)
    source: str | None = Field(default=None, max_length=64)
    value_paise: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _validate_budget(self) -> OpportunityCreateRequest:
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_min > self.budget_max
        ):
            raise ValueError("budget_min must not be greater than budget_max.")
        return self


class OpportunityUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    stage: OpportunityStage | None = None
    owner_user_id: UUID | None = None
    budget_min: int | None = Field(default=None, ge=0, le=_BUDGET_MAX)
    budget_max: int | None = Field(default=None, ge=0, le=_BUDGET_MAX)
    preferred_configuration: str | None = Field(default=None, max_length=100)
    loss_reason: str | None = Field(default=None, max_length=500)
    won_booking_id: UUID | None = None
    value_paise: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _require_field(self) -> OpportunityUpdateRequest:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        return self


class OpportunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contact_id: UUID
    project_id: UUID
    lead_id: UUID | None = None
    stage: OpportunityStage
    owner_user_id: UUID | None = None
    budget_min: int | None = None
    budget_max: int | None = None
    preferred_configuration: str | None = None
    source: str | None = None
    loss_reason: str | None = None
    won_booking_id: UUID | None = None
    value_paise: int | None = None
    created_at: datetime
    updated_at: datetime


class OpportunityListResponse(BaseModel):
    items: list[OpportunityResponse]
    total: int
    page: int
    page_size: int
    pages: int


class MergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    merged_id: UUID
    reason: str | None = Field(default=None, max_length=500)


class MergeEvidenceField(BaseModel):
    kind: str
    value: str
    normalized_value: str


class MergeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    survivor_id: UUID
    merged_id: UUID
    actor_user_id: UUID | None = None
    reason: str | None = None
    evidence: dict
    reverted_at: datetime | None = None
    created_at: datetime


class DuplicateCandidate(BaseModel):
    contact_id: UUID
    display_name: str
    confidence: str  # EXACT | HIGH
    matched_fields: list[MergeEvidenceField]
    evidence: str


class DuplicateSuggestionsResponse(BaseModel):
    contact_id: UUID
    candidates: list[DuplicateCandidate]


class TimelineItem(BaseModel):
    type: str
    occurred_at: datetime
    actor: str | None = None
    summary: str
    link_ids: dict[str, str] = {}


class Customer360Response(BaseModel):
    contact: ContactDetailResponse
    opportunities: list[OpportunityResponse]
    timeline: list[TimelineItem]
    freshness: dict[str, datetime | None]
