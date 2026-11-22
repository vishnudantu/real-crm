"""Staff-only internal chat endpoints; buyers are rejected by the role guard."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.teamchat import service
from app.modules.teamchat.schemas import (
    ChatChannelCreateRequest,
    ChatChannelListResponse,
    ChatChannelMemberResponse,
    ChatChannelResponse,
    ChatMessageCreateRequest,
    ChatMessageListResponse,
    ChatMessageResponse,
    ChatMessageUpdateRequest,
    ChatStaffUserResponse,
)
from app.modules.users.models import RoleName, User

StaffUser = Annotated[
    User, Depends(require_roles(RoleName.ADMIN, RoleName.SALES_EXECUTIVE))
]
Database = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/team-chat", tags=["team-chat"])
legacy_router = APIRouter(prefix="/teamchat", tags=["team-chat"], include_in_schema=False)


@router.post(
    "/channels",
    response_model=ChatChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_channel_endpoint(
    payload: ChatChannelCreateRequest, actor: StaffUser, db: Database
) -> ChatChannelResponse:
    return service.create_channel(db, actor=actor, payload=payload)


@router.get("/channels", response_model=ChatChannelListResponse)
def list_channels_endpoint(
    actor: StaffUser, db: Database
) -> ChatChannelListResponse:
    return service.list_channels(db, actor=actor)


@router.post("/channels/{channel_id}/join", response_model=ChatChannelResponse)
def join_channel_endpoint(
    channel_id: UUID, actor: StaffUser, db: Database
) -> ChatChannelResponse:
    return service.join_channel(db, actor=actor, channel_id=channel_id)


@router.post("/channels/{channel_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_channel_endpoint(
    channel_id: UUID, actor: StaffUser, db: Database
) -> None:
    service.leave_channel(db, actor=actor, channel_id=channel_id)


@router.get(
    "/channels/{channel_id}/members", response_model=list[ChatChannelMemberResponse]
)
def list_members_endpoint(
    channel_id: UUID, actor: StaffUser, db: Database
) -> list[ChatChannelMemberResponse]:
    return service.list_members(db, actor=actor, channel_id=channel_id)


@router.post(
    "/channels/{channel_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_message_endpoint(
    channel_id: UUID,
    payload: ChatMessageCreateRequest,
    actor: StaffUser,
    db: Database,
) -> ChatMessageResponse:
    return service.post_message(db, actor=actor, channel_id=channel_id, payload=payload)


@router.get("/channels/{channel_id}/messages", response_model=ChatMessageListResponse)
def list_messages_endpoint(
    channel_id: UUID,
    actor: StaffUser,
    db: Database,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    before: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
) -> ChatMessageListResponse:
    return service.list_messages(
        db,
        actor=actor,
        channel_id=channel_id,
        page=page,
        page_size=page_size,
        before=before,
        limit=limit,
    )


@router.patch("/messages/{message_id}", response_model=ChatMessageResponse)
def edit_message_endpoint(
    message_id: UUID,
    payload: ChatMessageUpdateRequest,
    actor: StaffUser,
    db: Database,
) -> ChatMessageResponse:
    return service.edit_message(db, actor=actor, message_id=message_id, payload=payload)


@legacy_router.get("/members", response_model=list[ChatStaffUserResponse])
def list_staff_endpoint(
    actor: StaffUser,
    db: Database,
    search: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ChatStaffUserResponse]:
    return [
        ChatStaffUserResponse(
            id=user.id, full_name=user.full_name, email=user.email, role=user.role.name
        )
        for user in service.list_staff(db, actor=actor, search=search, limit=limit)
    ]


# Keep the previous frontend operational while clients move to /team-chat.
legacy_router.post("/channels", status_code=status.HTTP_201_CREATED)(create_channel_endpoint)
legacy_router.get("/channels")(list_channels_endpoint)
legacy_router.post("/channels/{channel_id}/join")(join_channel_endpoint)
legacy_router.post("/channels/{channel_id}/leave", status_code=status.HTTP_204_NO_CONTENT)(
    leave_channel_endpoint
)
legacy_router.get("/channels/{channel_id}/members")(list_members_endpoint)
legacy_router.post("/channels/{channel_id}/messages", status_code=status.HTTP_201_CREATED)(
    post_message_endpoint
)
legacy_router.get("/channels/{channel_id}/messages")(list_messages_endpoint)
legacy_router.patch("/messages/{message_id}")(edit_message_endpoint)
