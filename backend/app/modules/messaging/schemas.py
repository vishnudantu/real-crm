"""Pydantic contracts for the tenant messaging admin API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.messaging.models import DeliveryStatus, MessageChannel


class MessageTemplateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=128)
    channel: MessageChannel
    language: str = Field(default="en", min_length=2, max_length=8, pattern=r"^[a-z]{2,8}$")
    body: str = Field(min_length=1, max_length=4000)
    provider_template_name: str | None = Field(default=None, max_length=160)
    variables: list[str] = Field(default_factory=list, max_length=25)


class MessageTemplateUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=128)
    body: str | None = Field(default=None, min_length=1, max_length=4000)
    provider_template_name: str | None = Field(default=None, max_length=160)
    variables: list[str] | None = Field(default=None, max_length=25)
    is_active: bool | None = None


class MessageTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    channel: MessageChannel
    language: str
    body: str
    provider_template_name: str | None
    variables: list
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MessageTemplateListResponse(BaseModel):
    items: list[MessageTemplateResponse]
    total: int


class TriggerRuleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_.]+$")
    channel: MessageChannel
    template_id: UUID
    enabled: bool = True
    delay_minutes: int = Field(default=0, ge=0, le=10080)


class TriggerRuleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    delay_minutes: int | None = Field(default=None, ge=0, le=10080)
    template_id: UUID | None = None


class TriggerRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event: str
    channel: MessageChannel
    template_id: UUID
    enabled: bool
    delay_minutes: int
    created_at: datetime
    updated_at: datetime


class TriggerRuleListResponse(BaseModel):
    items: list[TriggerRuleResponse]
    total: int


class MessageDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel: MessageChannel
    to_address: str
    body: str
    provider: str
    status: DeliveryStatus
    provider_msg_id: str | None
    error: str | None
    attempts: int
    event: str
    entity_type: str | None
    entity_id: UUID | None
    next_attempt_at: datetime
    sent_at: datetime | None
    created_at: datetime


class MessageDeliveryListResponse(BaseModel):
    items: list[MessageDeliveryResponse]
    total: int
    page: int
    page_size: int
    pages: int


class SendTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    channel: MessageChannel
    to_address: str = Field(min_length=3, max_length=320)
    template_id: UUID | None = None
    body: str | None = Field(default=None, min_length=1, max_length=4000)
