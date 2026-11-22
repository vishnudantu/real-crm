"""Public API contracts for the broker registry and performance."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.brokers.models import BrokerStatus


class BrokerCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    agency_name: str = Field(min_length=1, max_length=255)
    contact_name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    rera_id: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=4000)


class BrokerUpdateRequest(BaseModel):
    """Editable contact/status fields only; agency identity needs a rename flow."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    contact_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    rera_id: str | None = Field(default=None, max_length=64)
    status: BrokerStatus | None = None
    notes: str | None = Field(default=None, max_length=4000)


class BrokerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    agency_name: str
    contact_name: str
    email: str | None
    phone: str | None
    rera_id: str | None
    status: BrokerStatus
    notes: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class BrokerListResponse(BaseModel):
    items: list[BrokerResponse]
    total: int


class BrokerPerformanceResponse(BaseModel):
    broker_id: UUID
    total_commission_paise: int
    by_status: dict[str, int]
    deal_count: int
