"""Pydantic contracts for omnichannel configuration, inbox, and calling."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.omnichannel.models import ChannelType


class ChannelCredentialUpsert(BaseModel):
    channel: ChannelType
    provider: str = Field(min_length=2, max_length=64)
    credentials: dict = Field(default_factory=dict)
    config: dict = Field(default_factory=dict)
    is_active: bool = True
    webhook_verify_token: str | None = Field(default=None, max_length=255)


class ChannelCredentialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel: str
    provider: str
    config: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Never expose credentials_ciphertext or webhook_verify_token_hash.


class ChannelMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conversation_id: UUID
    channel: str
    direction: str
    sender_id: UUID | None
    sender_handle: str | None
    external_message_id: str | None
    content_type: str
    content: str | None
    media_url: str | None
    status: str
    error: str | None
    created_at: datetime


class ChannelConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID | None
    contact_id: UUID | None
    assigned_to_id: UUID | None
    channel: str
    external_thread_id: str
    contact_name: str | None
    contact_handle: str | None
    contact_avatar_url: str | None
    status: str
    last_message_preview: str | None
    last_message_at: datetime | None
    unread_count: int
    created_at: datetime
    updated_at: datetime


class ChannelConversationDetail(ChannelConversationResponse):
    messages: list[ChannelMessageResponse] = Field(default_factory=list)


class InboxResponse(BaseModel):
    items: list[ChannelConversationResponse]
    total: int
    unread_total: int


class SendChannelMessageRequest(BaseModel):
    conversation_id: UUID
    text: str = Field(min_length=1, max_length=4000)


class AssignConversationRequest(BaseModel):
    assigned_to_id: UUID | None


class CallStartRequest(BaseModel):
    lead_id: UUID | None = None
    conversation_id: UUID | None = None
    destination: str | None = Field(default=None, max_length=255)
    record: bool = False
    recording_consent_confirmed: bool = False


class CallJoinRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)


class CallResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID | None
    conversation_id: UUID | None
    agent_id: UUID
    direction: str
    status: str
    provider: str
    room_name: str
    destination: str | None
    duration_seconds: int
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime


class CallTokenResponse(BaseModel):
    call: CallResponse
    participant_token: str
    connection: dict


class CallRecordingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    call_id: UUID
    egress_id: str | None
    status: str
    storage_url: str | None
    mime_type: str
    duration_seconds: int
    size_bytes: int
    created_at: datetime
    completed_at: datetime | None
