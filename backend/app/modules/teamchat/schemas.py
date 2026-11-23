"""API contracts for the internal staff chat."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TeamChannelCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    topic: str | None = Field(default=None, max_length=500)
    # Alias accepted by the /team-chat compatibility router; mapped to topic.
    description: str | None = Field(default=None, max_length=500)
    member_ids: list[UUID] = Field(default_factory=list, max_length=100)
    # Optional private-channel flag accepted by the /team-chat alias; public
    # staff channels (the default) are joinable by any staff member.
    is_private: bool = False

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("topic", mode="before")
    @classmethod
    def normalize_topic(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return value.strip() or None


class TeamDirectCreateRequest(BaseModel):
    user_id: UUID


class TeamMessageCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    mentions: list[UUID] = Field(default_factory=list, max_length=100)


class TeamMessageEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body", mode="before")
    @classmethod
    def normalize_body(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class TeamStaffUserResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    role: str


class TeamChannelMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    role: str
    joined_at: datetime
    last_read_at: datetime | None
    user: TeamStaffUserResponse | None = None


class TeamChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    topic: str | None
    kind: str
    is_general: bool
    is_private: bool = False
    created_by: UUID | None
    created_at: datetime
    unread_count: int = 0
    member_count: int = 0
    members: list[TeamChannelMemberResponse] = Field(default_factory=list)


class TeamChannelListResponse(BaseModel):
    items: list[TeamChannelResponse]
    total: int
    unread_total: int


class TeamMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel_id: UUID
    author_user_id: UUID | None
    author: TeamStaffUserResponse | None = None
    body: str
    mentions: list[UUID]
    created_at: datetime
    edited_at: datetime | None


class TeamMessageListResponse(BaseModel):
    items: list[TeamMessageResponse]
    next_before: str | None


class TeamUnreadResponse(BaseModel):
    total: int
    by_channel: dict[str, int]


class TeamReadResponse(BaseModel):
    channel_id: UUID
    last_read_at: datetime
