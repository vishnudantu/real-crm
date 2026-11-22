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
    TeamChannelCreateRequest,
    TeamChannelListResponse,
    TeamChannelResponse,
    TeamDirectCreateRequest,
    TeamMessageCreateRequest,
    TeamMessageListResponse,
    TeamMessageResponse,
    TeamReadResponse,
    TeamStaffUserResponse,
    TeamUnreadResponse,
)
from app.modules.users.models import RoleName, User

router = APIRouter(prefix="/teamchat", tags=["teamchat"])
StaffUser = Annotated[
    User, Depends(require_roles(RoleName.ADMIN, RoleName.SALES_EXECUTIVE))
]
Database = Annotated[Session, Depends(get_db)]


@router.get("/channels", response_model=TeamChannelListResponse)
def list_channels(actor: StaffUser, db: Database) -> TeamChannelListResponse:
    items, unread_total = service.list_channels(db, actor=actor)
    return TeamChannelListResponse(items=items, total=len(items), unread_total=unread_total)


@router.post("/channels", response_model=TeamChannelResponse, status_code=status.HTTP_201_CREATED)
def create_channel(
    payload: TeamChannelCreateRequest, actor: StaffUser, db: Database
) -> TeamChannelResponse:
    return service.create_channel(db, actor=actor, payload=payload)


@router.post("/channels/general", response_model=TeamChannelResponse)
def ensure_general(actor: StaffUser, db: Database) -> TeamChannelResponse:
    return service.ensure_general_channel(db, actor=actor)


@router.post("/direct", response_model=TeamChannelResponse, status_code=status.HTTP_201_CREATED)
def create_direct(
    payload: TeamDirectCreateRequest, actor: StaffUser, db: Database
) -> TeamChannelResponse:
    return service.create_direct(db, actor=actor, user_id=payload.user_id)


@router.get("/unread", response_model=TeamUnreadResponse)
def unread_totals(actor: StaffUser, db: Database) -> TeamUnreadResponse:
    total, by_channel = service.list_unread_totals(db, actor=actor)
    return TeamUnreadResponse(total=total, by_channel=by_channel)


@router.get("/members", response_model=list[TeamStaffUserResponse])
def search_staff(
    actor: StaffUser,
    db: Database,
    search: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[TeamStaffUserResponse]:
    return [
        TeamStaffUserResponse(id=user.id, full_name=user.full_name, email=user.email, role=user.role.name)
        for user in service.list_staff(db, actor=actor, search=search, limit=limit)
    ]


@router.get("/channels/{channel_id}/messages", response_model=TeamMessageListResponse)
def list_messages(
    channel_id: UUID,
    actor: StaffUser,
    db: Database,
    before: Annotated[str | None, Query(max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 50,
) -> TeamMessageListResponse:
    items, next_before = service.list_messages(
        db, actor=actor, channel_id=channel_id, before=before, limit=limit
    )
    return TeamMessageListResponse(items=items, next_before=next_before)


@router.post(
    "/channels/{channel_id}/messages",
    response_model=TeamMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    channel_id: UUID, payload: TeamMessageCreateRequest, actor: StaffUser, db: Database
) -> TeamMessageResponse:
    return service.send_message(db, actor=actor, channel_id=channel_id, payload=payload)


@router.post("/channels/{channel_id}/read", response_model=TeamReadResponse)
def mark_read(channel_id: UUID, actor: StaffUser, db: Database) -> TeamReadResponse:
    membership = service.mark_read(db, actor=actor, channel_id=channel_id)
    return TeamReadResponse(channel_id=channel_id, last_read_at=membership.last_read_at)


@router.post("/channels/{channel_id}/join", response_model=TeamChannelResponse)
def join_channel(channel_id: UUID, actor: StaffUser, db: Database) -> TeamChannelResponse:
    return service.join_channel(db, actor=actor, channel_id=channel_id)


@router.post("/channels/{channel_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_channel(channel_id: UUID, actor: StaffUser, db: Database) -> None:
    service.leave_channel(db, actor=actor, channel_id=channel_id)
