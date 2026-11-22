"""API contracts for internal staff-to-staff chat."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatChannelCreateRequest(BaseModel):
    """Input for creating a channel and its initial membership."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    is_private: bool = False
    member_ids: list[UUID] = Field(default_factory=list, max_length=100)

    @field_validator("description", mode="before")
    @classmethod
    def _empty_description_as_none(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


class ChatStaffUserResponse(BaseModel):
    """Non-sensitive staff identity included in member and message responses."""

    id: UUID
    full_name: str
    email: str
    role: str


class ChatChannelMemberResponse(BaseModel):
    """A channel membership and its staff identity."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel_id: UUID
    user_id: UUID
    role: str
    joined_at: datetime
    user: ChatStaffUserResponse


class ChatChannelResponse(BaseModel):
    """Representation of an internal chat channel."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    is_private: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    member_count: int = 0
    members: list[ChatChannelMemberResponse] = Field(default_factory=list)


class ChatChannelListResponse(BaseModel):
    """Channels visible to the current staff member."""

    items: list[ChatChannelResponse]
    total: int


class ChatMessageCreateRequest(BaseModel):
    """Input for posting a staff message."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body", mode="before")
    @classmethod
    def _require_non_empty_body(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            raise ValueError("Message body cannot be empty.")
        return value


class ChatMessageUpdateRequest(ChatMessageCreateRequest):
    """Input for editing a staff message."""


class ChatMessageResponse(BaseModel):
    """Representation of an individual staff message."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel_id: UUID
    sender_user_id: UUID | None
    sender: ChatStaffUserResponse | None = None
    body: str
    created_at: datetime
    updated_at: datetime
    edited_at: datetime | None


class ChatMessageListResponse(BaseModel):
    """A newest-first page of channel messages."""

    items: list[ChatMessageResponse]
    total: int
    page: int
    page_size: int
    pages: int
    next_before: str | None = None
