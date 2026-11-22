"""Business logic and authorization for internal staff chat."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.modules.teamchat import repository
from app.modules.teamchat.exceptions import (
    ChatChannelNameConflictError,
    ChatChannelNotFoundError,
    ChatChannelPrivateError,
    ChatMembershipRequiredError,
    ChatMessageEditForbiddenError,
    ChatMessageNotFoundError,
)
from app.modules.teamchat.models import (
    ChatChannel,
    ChatChannelMember,
    ChatChannelRole,
    ChatMessage,
    utcnow,
)
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
from app.modules.users.models import Role, RoleName, User

STAFF_ROLES = (RoleName.ADMIN.value, RoleName.SALES_EXECUTIVE.value)


def _staff_response(user: User | None) -> ChatStaffUserResponse | None:
    if user is None:
        return None
    return ChatStaffUserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role.name,
    )


def _member_response(member: ChatChannelMember) -> ChatChannelMemberResponse:
    return ChatChannelMemberResponse(
        id=member.id,
        channel_id=member.channel_id,
        user_id=member.user_id,
        role=member.role,
        joined_at=member.joined_at,
        user=_staff_response(member.user),
    )


def _message_response(message: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=message.id,
        channel_id=message.channel_id,
        sender_user_id=message.sender_user_id,
        sender=_staff_response(message.sender),
        body=message.body,
        created_at=message.created_at,
        updated_at=message.updated_at,
        edited_at=message.edited_at,
    )


def _channel(session: Session, *, actor: User, channel_id: UUID) -> ChatChannel:
    channel = repository.get_channel_by_id(
        session, channel_id, tenant_id=actor.tenant_id
    )
    if channel is None:
        raise ChatChannelNotFoundError()
    return channel


def _membership(
    session: Session, *, actor: User, channel_id: UUID
) -> ChatChannelMember | None:
    return repository.get_membership(
        session,
        tenant_id=actor.tenant_id,
        channel_id=channel_id,
        user_id=actor.id,
    )


def _require_membership(
    session: Session, *, actor: User, channel_id: UUID
) -> ChatChannelMember:
    membership = _membership(session, actor=actor, channel_id=channel_id)
    if membership is None:
        raise ChatMembershipRequiredError()
    return membership


def _tenant_staff(
    session: Session, *, tenant_id: UUID, user_ids: list[UUID]
) -> list[User]:
    unique_ids = set(user_ids)
    if not unique_ids:
        return []
    users = list(
        session.scalars(
            select(User)
            .join(Role, User.role_id == Role.id)
            .where(
                User.tenant_id == tenant_id,
                User.id.in_(unique_ids),
                User.is_active.is_(True),
                Role.name.in_(STAFF_ROLES),
            )
        ).all()
    )
    if len(users) != len(unique_ids):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Every member must be an active staff user in your organization.",
        )
    return users


def _channel_response(
    channel: ChatChannel,
    *,
    member_count: int,
    members: list[ChatChannelMemberResponse] | None = None,
) -> ChatChannelResponse:
    return ChatChannelResponse(
        id=channel.id,
        name=channel.name,
        description=channel.description,
        is_private=channel.is_private,
        created_by=channel.created_by,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
        member_count=member_count,
        members=members or [],
    )


def _channel_with_members(session: Session, *, channel: ChatChannel) -> ChatChannelResponse:
    members = repository.list_members(
        session, tenant_id=channel.tenant_id, channel_id=channel.id
    )
    return _channel_response(
        channel,
        member_count=len(members),
        members=[_member_response(member) for member in members],
    )


def create_channel(
    session: Session, *, actor: User, payload: ChatChannelCreateRequest
) -> ChatChannelResponse:
    """Create a channel, automatically joining its creator as an admin."""

    _tenant_staff(session, tenant_id=actor.tenant_id, user_ids=payload.member_ids)
    if repository.get_channel_by_name(
        session, tenant_id=actor.tenant_id, name=payload.name
    ) is not None:
        raise ChatChannelNameConflictError()

    now = utcnow()
    channel = ChatChannel(
        tenant_id=actor.tenant_id,
        name=payload.name,
        description=payload.description,
        is_private=payload.is_private,
        created_by=actor.id,
        created_at=now,
        updated_at=now,
    )
    session.add(channel)
    try:
        session.flush()
        for user_id in {actor.id, *payload.member_ids}:
            session.add(
                ChatChannelMember(
                    tenant_id=actor.tenant_id,
                    channel_id=channel.id,
                    user_id=user_id,
                    role=(
                        ChatChannelRole.ADMIN.value
                        if user_id == actor.id
                        else ChatChannelRole.MEMBER.value
                    ),
                    joined_at=now,
                )
            )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise ChatChannelNameConflictError() from exc
    session.refresh(channel)
    return _channel_with_members(session, channel=channel)


def join_channel(
    session: Session, *, actor: User, channel_id: UUID
) -> ChatChannelResponse:
    """Join a public channel; private channels require an invitation."""

    channel = _channel(session, actor=actor, channel_id=channel_id)
    membership = _membership(session, actor=actor, channel_id=channel.id)
    if membership is not None:
        return _channel_with_members(session, channel=channel)
    if channel.is_private:
        raise ChatChannelPrivateError()
    session.add(
        ChatChannelMember(
            tenant_id=actor.tenant_id,
            channel_id=channel.id,
            user_id=actor.id,
            role=ChatChannelRole.MEMBER.value,
        )
    )
    session.commit()
    return _channel_with_members(session, channel=channel)


def leave_channel(session: Session, *, actor: User, channel_id: UUID) -> None:
    """Remove the current user's membership from a channel."""

    channel = _channel(session, actor=actor, channel_id=channel_id)
    membership = _require_membership(session, actor=actor, channel_id=channel.id)
    session.delete(membership)
    session.commit()


def list_channels(session: Session, *, actor: User) -> ChatChannelListResponse:
    """List public channels and private channels the user belongs to."""

    channels = repository.list_visible_channels(
        session, tenant_id=actor.tenant_id, user_id=actor.id
    )
    counts = repository.member_count_map(session, tenant_id=actor.tenant_id)
    return ChatChannelListResponse(
        items=[
            _channel_response(channel, member_count=counts.get(channel.id, 0))
            for channel in channels
        ],
        total=len(channels),
    )


def list_members(
    session: Session, *, actor: User, channel_id: UUID
) -> list[ChatChannelMemberResponse]:
    """List members only after verifying the caller is a member."""

    channel = _channel(session, actor=actor, channel_id=channel_id)
    _require_membership(session, actor=actor, channel_id=channel.id)
    return [
        _member_response(member)
        for member in repository.list_members(
            session, tenant_id=actor.tenant_id, channel_id=channel.id
        )
    ]


def post_message(
    session: Session,
    *,
    actor: User,
    channel_id: UUID,
    payload: ChatMessageCreateRequest,
) -> ChatMessageResponse:
    """Post a message as the current member of a channel."""

    channel = _channel(session, actor=actor, channel_id=channel_id)
    _require_membership(session, actor=actor, channel_id=channel.id)
    now = utcnow()
    message = ChatMessage(
        tenant_id=actor.tenant_id,
        channel_id=channel.id,
        sender_user_id=actor.id,
        body=payload.body,
        created_at=now,
        updated_at=now,
    )
    session.add(message)
    channel.updated_at = now
    session.commit()
    session.refresh(message)
    return _message_response(message)


def _decode_before(before: str | None) -> tuple[datetime, UUID] | None:
    if before is None:
        return None
    try:
        raw = base64.urlsafe_b64decode(before.encode("ascii")).decode("ascii")
        timestamp, identifier = json.loads(raw)
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")), UUID(identifier)
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid message cursor."
        ) from exc


def _encode_before(message: ChatMessage) -> str:
    value = json.dumps(
        [message.created_at.isoformat(), str(message.id)], separators=(",", ":")
    )
    return base64.urlsafe_b64encode(value.encode("ascii")).decode("ascii")


def list_messages(
    session: Session,
    *,
    actor: User,
    channel_id: UUID,
    page: int = 1,
    page_size: int = 50,
    before: str | None = None,
    limit: int | None = None,
) -> ChatMessageListResponse:
    """Return a member-only, newest-first page of channel messages."""

    channel = _channel(session, actor=actor, channel_id=channel_id)
    _require_membership(session, actor=actor, channel_id=channel.id)
    page_size = limit if limit is not None else page_size
    cursor = _decode_before(before)
    messages = repository.list_messages(
        session,
        tenant_id=actor.tenant_id,
        channel_id=channel.id,
        offset=(page - 1) * page_size,
        limit=page_size + 1,
        cursor=cursor,
    )
    has_more = len(messages) > page_size
    items = messages[:page_size]
    total = repository.count_messages(
        session, tenant_id=actor.tenant_id, channel_id=channel.id
    )
    return ChatMessageListResponse(
        items=[_message_response(message) for message in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total else 0,
        next_before=_encode_before(items[-1]) if has_more and items else None,
    )


def edit_message(
    session: Session,
    *,
    actor: User,
    message_id: UUID,
    payload: ChatMessageUpdateRequest,
) -> ChatMessageResponse:
    """Edit only the caller's own message and record its edit timestamp."""

    message = repository.get_message_by_id(
        session, message_id, tenant_id=actor.tenant_id
    )
    if message is None:
        raise ChatMessageNotFoundError()
    _channel(session, actor=actor, channel_id=message.channel_id)
    _require_membership(session, actor=actor, channel_id=message.channel_id)
    if message.sender_user_id != actor.id:
        raise ChatMessageEditForbiddenError()
    now = utcnow()
    message.body = payload.body
    message.edited_at = now
    message.updated_at = now
    session.commit()
    session.refresh(message)
    return _message_response(message)


def list_staff(
    session: Session, *, actor: User, search: str | None, limit: int
) -> list[User]:
    """Find active staff in the caller's tenant for channel invitations."""

    statement = (
        select(User)
        .join(Role, User.role_id == Role.id)
        .where(
            User.tenant_id == actor.tenant_id,
            User.is_active.is_(True),
            Role.name.in_(STAFF_ROLES),
        )
    )
    needle = (search or "").strip()
    if needle:
        pattern = f"%{needle.lower()}%"
        statement = statement.where(
            or_(
                func.lower(User.full_name).like(pattern),
                func.lower(User.email).like(pattern),
            )
        )
    return list(session.scalars(statement.order_by(User.full_name, User.id).limit(limit)).all())
