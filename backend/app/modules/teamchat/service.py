"""Team chat domain services with explicit tenant and membership predicates."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, joinedload

from app.modules.teamchat.models import (
    TeamChannel,
    TeamChannelKind,
    TeamChannelMember,
    TeamChannelRole,
    TeamMessage,
    utcnow,
)
from app.modules.teamchat.schemas import (
    TeamChannelCreateRequest,
    TeamChannelMemberResponse,
    TeamChannelResponse,
    TeamMessageCreateRequest,
    TeamMessageResponse,
    TeamStaffUserResponse,
)
from app.modules.users.models import Role, RoleName, User

STAFF_ROLES = (RoleName.ADMIN.value, RoleName.SALES_EXECUTIVE.value)
DEFAULT_PAGE_SIZE = 50


def _staff_response(user: User | None) -> TeamStaffUserResponse | None:
    if user is None:
        return None
    return TeamStaffUserResponse(
        id=user.id, full_name=user.full_name, email=user.email, role=user.role.name
    )


def _channel(session: Session, *, tenant_id: UUID, channel_id: UUID) -> TeamChannel:
    channel = session.scalar(
        select(TeamChannel).where(
            TeamChannel.id == channel_id, TeamChannel.tenant_id == tenant_id
        )
    )
    if channel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team channel not found.")
    return channel


def _membership(
    session: Session, *, tenant_id: UUID, channel_id: UUID, user_id: UUID
) -> TeamChannelMember | None:
    return session.scalar(
        select(TeamChannelMember).where(
            TeamChannelMember.tenant_id == tenant_id,
            TeamChannelMember.channel_id == channel_id,
            TeamChannelMember.user_id == user_id,
        )
    )


def _require_membership(
    session: Session, *, tenant_id: UUID, channel_id: UUID, user_id: UUID
) -> TeamChannelMember:
    membership = _membership(
        session, tenant_id=tenant_id, channel_id=channel_id, user_id=user_id
    )
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Join this channel before continuing.")
    return membership


def _tenant_staff(session: Session, *, tenant_id: UUID, user_ids: list[UUID]) -> list[User]:
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
            "Every member and mention must be an active staff user in your organization.",
        )
    return users


def _unread_counts(
    session: Session, *, tenant_id: UUID, user_id: UUID
) -> dict[UUID, int]:
    membership = aliased(TeamChannelMember)
    rows = session.execute(
        select(membership.channel_id, func.count(TeamMessage.id))
        .join(
            TeamMessage,
            and_(
                TeamMessage.tenant_id == membership.tenant_id,
                TeamMessage.channel_id == membership.channel_id,
                TeamMessage.author_user_id != user_id,
                or_(
                    membership.last_read_at.is_(None),
                    TeamMessage.created_at > membership.last_read_at,
                ),
            ),
        )
        .where(membership.tenant_id == tenant_id, membership.user_id == user_id)
        .group_by(membership.channel_id)
    ).all()
    return {channel_id: int(count) for channel_id, count in rows}


def _channel_response(
    channel: TeamChannel, *, unread: int, member_count: int = 0,
    members: list[TeamChannelMemberResponse] | None = None,
) -> TeamChannelResponse:
    return TeamChannelResponse(
        id=channel.id,
        name=channel.name,
        topic=channel.topic,
        kind=channel.kind,
        is_general=channel.is_general,
        created_by=channel.created_by,
        created_at=channel.created_at,
        unread_count=unread,
        member_count=member_count,
        members=members or [],
    )


def _channel_with_members(
    session: Session, *, channel: TeamChannel, unread: int
) -> TeamChannelResponse:
    rows = session.execute(
        select(TeamChannelMember, User)
        .join(User, User.id == TeamChannelMember.user_id)
        .where(
            TeamChannelMember.tenant_id == channel.tenant_id,
            TeamChannelMember.channel_id == channel.id,
            User.tenant_id == channel.tenant_id,
        )
        .order_by(TeamChannelMember.joined_at, TeamChannelMember.id)
    ).all()
    return _channel_response(
        channel, unread=unread, member_count=len(rows),
        members=[
            TeamChannelMemberResponse(
                user_id=member.user_id,
                role=member.role,
                joined_at=member.joined_at,
                last_read_at=member.last_read_at,
                user=_staff_response(user),
            )
            for member, user in rows
        ],
    )


def _member_count_map(session: Session, *, tenant_id: UUID) -> dict[UUID, int]:
    rows = session.execute(
        select(TeamChannelMember.channel_id, func.count(TeamChannelMember.id))
        .where(TeamChannelMember.tenant_id == tenant_id)
        .group_by(TeamChannelMember.channel_id)
    ).all()
    return {channel_id: int(count) for channel_id, count in rows}


def create_channel(
    session: Session, *, actor: User, payload: TeamChannelCreateRequest
) -> TeamChannelResponse:
    _tenant_staff(session, tenant_id=actor.tenant_id, user_ids=payload.member_ids)
    existing = session.scalar(
        select(TeamChannel).where(
            TeamChannel.tenant_id == actor.tenant_id, TeamChannel.name == payload.name
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A channel with this name already exists.")
    channel = TeamChannel(
        tenant_id=actor.tenant_id, name=payload.name, topic=payload.topic,
        kind=TeamChannelKind.CHANNEL.value, created_by=actor.id,
    )
    session.add(channel)
    try:
        session.flush()
        member_ids = {actor.id, *payload.member_ids}
        for user_id in member_ids:
            session.add(TeamChannelMember(
                tenant_id=actor.tenant_id, channel_id=channel.id, user_id=user_id,
                role=(TeamChannelRole.OWNER.value if user_id == actor.id
                      else TeamChannelRole.MEMBER.value),
            ))
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A channel with this name already exists."
        ) from exc
    return _channel_with_members(session, channel=channel, unread=0)


def ensure_general_channel(session: Session, *, actor: User) -> TeamChannelResponse:
    channel = session.scalar(
        select(TeamChannel).where(
            TeamChannel.tenant_id == actor.tenant_id, TeamChannel.is_general.is_(True)
        )
    )
    if channel is not None:
        if _membership(
            session, tenant_id=actor.tenant_id, channel_id=channel.id, user_id=actor.id
        ) is None:
            return join_channel(session, actor=actor, channel_id=channel.id)
        unread = _unread_counts(session, tenant_id=actor.tenant_id, user_id=actor.id)
        return _channel_with_members(
            session, channel=channel, unread=unread.get(channel.id, 0)
        )
    if actor.role.name != RoleName.ADMIN.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "An administrator must create the general channel first."
        )
    channel = TeamChannel(
        tenant_id=actor.tenant_id, name="general", topic="Company-wide staff updates",
        kind=TeamChannelKind.CHANNEL.value, is_general=True, created_by=actor.id,
    )
    session.add(channel)
    session.flush()
    staff_users = list(session.scalars(
        select(User).where(User.tenant_id == actor.tenant_id, User.is_active.is_(True))
    ).all())
    for user in staff_users:
        if user.role.name not in STAFF_ROLES:
            continue
        session.add(TeamChannelMember(
            tenant_id=actor.tenant_id, channel_id=channel.id, user_id=user.id,
            role=(TeamChannelRole.OWNER.value if user.id == actor.id else TeamChannelRole.MEMBER.value),
        ))
    session.commit()
    return _channel_with_members(session, channel=channel, unread=0)


def create_direct(session: Session, *, actor: User, user_id: UUID) -> TeamChannelResponse:
    recipient = _tenant_staff(session, tenant_id=actor.tenant_id, user_ids=[user_id])[0]
    if recipient.id == actor.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose another staff member for a direct chat.")
    own_memberships = select(TeamChannelMember.channel_id).where(
        TeamChannelMember.tenant_id == actor.tenant_id,
        TeamChannelMember.user_id == actor.id,
    )
    pair_memberships = select(TeamChannelMember.channel_id).where(
        TeamChannelMember.tenant_id == actor.tenant_id,
        TeamChannelMember.channel_id.in_(own_memberships),
        TeamChannelMember.user_id == recipient.id,
    )
    channels = list(session.scalars(
        select(TeamChannel).where(
            TeamChannel.tenant_id == actor.tenant_id,
            TeamChannel.kind == TeamChannelKind.DIRECT.value,
            TeamChannel.id.in_(pair_memberships),
        ).order_by(TeamChannel.created_at)
    ).all())
    for channel in channels:
        if _membership(
            session, tenant_id=actor.tenant_id, channel_id=channel.id, user_id=actor.id
        ) is not None:
            join_channel(session, actor=actor, channel_id=channel.id)
            unread = _unread_counts(session, tenant_id=actor.tenant_id, user_id=actor.id)
            return _channel_with_members(
                session, channel=channel, unread=unread.get(channel.id, 0)
            )
    channel = TeamChannel(
        tenant_id=actor.tenant_id, name=f"dm-{actor.id}-{recipient.id}",
        kind=TeamChannelKind.DIRECT.value, created_by=actor.id,
    )
    session.add(channel)
    session.flush()
    for member_id in (actor.id, recipient.id):
        session.add(TeamChannelMember(
            tenant_id=actor.tenant_id, channel_id=channel.id, user_id=member_id,
            role=TeamChannelRole.MEMBER.value,
        ))
    session.commit()
    return _channel_with_members(session, channel=channel, unread=0)


def join_channel(session: Session, *, actor: User, channel_id: UUID) -> TeamChannelResponse:
    channel = _channel(session, tenant_id=actor.tenant_id, channel_id=channel_id)
    membership = _membership(
        session, tenant_id=actor.tenant_id, channel_id=channel.id, user_id=actor.id
    )
    if membership is not None:
        unread = _unread_counts(session, tenant_id=actor.tenant_id, user_id=actor.id)
        return _channel_with_members(
            session, channel=channel, unread=unread.get(channel.id, 0)
        )
    session.add(TeamChannelMember(
        tenant_id=actor.tenant_id, channel_id=channel.id, user_id=actor.id,
        role=TeamChannelRole.MEMBER.value,
    ))
    session.commit()
    return _channel_with_members(session, channel=channel, unread=0)


def leave_channel(session: Session, *, actor: User, channel_id: UUID) -> None:
    channel = _channel(session, tenant_id=actor.tenant_id, channel_id=channel_id)
    membership = _require_membership(
        session, tenant_id=actor.tenant_id, channel_id=channel.id, user_id=actor.id
    )
    if channel.is_general:
        raise HTTPException(status.HTTP_409_CONFLICT, "The general channel cannot be left.")
    session.delete(membership)
    session.commit()


def list_channels(session: Session, *, actor: User) -> tuple[list[TeamChannelResponse], int]:
    channels = list(session.scalars(
        select(TeamChannel)
        .join(TeamChannelMember, TeamChannelMember.channel_id == TeamChannel.id)
        .where(
            TeamChannel.tenant_id == actor.tenant_id,
            TeamChannelMember.tenant_id == actor.tenant_id,
            TeamChannelMember.user_id == actor.id,
        )
        .order_by(TeamChannel.is_general.desc(), TeamChannel.created_at, TeamChannel.id)
    ).all())
    unread = _unread_counts(session, tenant_id=actor.tenant_id, user_id=actor.id)
    member_counts = _member_count_map(session, tenant_id=actor.tenant_id)
    items = [
        _channel_response(
            channel, unread=unread.get(channel.id, 0),
            member_count=member_counts.get(channel.id, 0),
        )
        for channel in channels
    ]
    return items, sum(unread.values())


def _decode_before(before: str | None) -> tuple[datetime, UUID] | None:
    if before is None:
        return None
    try:
        raw = base64.urlsafe_b64decode(before.encode("ascii")).decode("ascii")
        timestamp, identifier = json.loads(raw)
        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")), UUID(identifier)
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid message cursor.") from exc


def _encode_before(message: TeamMessage) -> str:
    value = json.dumps([message.created_at.isoformat(), str(message.id)], separators=(",", ":"))
    return base64.urlsafe_b64encode(value.encode("ascii")).decode("ascii")


def _message_response(message: TeamMessage) -> TeamMessageResponse:
    return TeamMessageResponse(
        id=message.id, channel_id=message.channel_id,
        author_user_id=message.author_user_id, author=_staff_response(message.author),
        body=message.body, mentions=[UUID(value) for value in message.mentions],
        created_at=message.created_at, edited_at=message.edited_at,
    )


def list_messages(
    session: Session, *, actor: User, channel_id: UUID,
    before: str | None = None, limit: int = DEFAULT_PAGE_SIZE,
) -> tuple[list[TeamMessageResponse], str | None]:
    _channel(session, tenant_id=actor.tenant_id, channel_id=channel_id)
    _require_membership(
        session, tenant_id=actor.tenant_id, channel_id=channel_id, user_id=actor.id
    )
    cursor = _decode_before(before)
    conditions = [
        TeamMessage.tenant_id == actor.tenant_id,
        TeamMessage.channel_id == channel_id,
    ]
    if cursor is not None:
        timestamp, identifier = cursor
        conditions.append(or_(
            TeamMessage.created_at < timestamp,
            and_(TeamMessage.created_at == timestamp, TeamMessage.id < identifier),
        ))
    messages = list(session.scalars(
        select(TeamMessage)
        .options(joinedload(TeamMessage.author))
        .where(*conditions)
        .order_by(TeamMessage.created_at.desc(), TeamMessage.id.desc())
        .limit(limit + 1)
    ).all())
    has_more = len(messages) > limit
    page = messages[:limit]
    return (
        [_message_response(message) for message in page],
        _encode_before(page[-1]) if has_more and page else None,
    )


def send_message(
    session: Session, *, actor: User, channel_id: UUID, payload: TeamMessageCreateRequest
) -> TeamMessageResponse:
    _channel(session, tenant_id=actor.tenant_id, channel_id=channel_id)
    _require_membership(
        session, tenant_id=actor.tenant_id, channel_id=channel_id, user_id=actor.id
    )
    body = payload.body.strip()
    if not 1 <= len(body) <= 4000:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Message body must contain 1 to 4000 characters.")
    _tenant_staff(session, tenant_id=actor.tenant_id, user_ids=payload.mentions)
    message = TeamMessage(
        tenant_id=actor.tenant_id, channel_id=channel_id, author_user_id=actor.id,
        body=body, mentions=[str(user_id) for user_id in dict.fromkeys(payload.mentions)],
    )
    session.add(message)
    session.commit()
    return _message_response(message)


def mark_read(
    session: Session, *, actor: User, channel_id: UUID
) -> TeamChannelMember:
    _channel(session, tenant_id=actor.tenant_id, channel_id=channel_id)
    membership = _require_membership(
        session, tenant_id=actor.tenant_id, channel_id=channel_id, user_id=actor.id
    )
    membership.last_read_at = utcnow()
    session.commit()
    return membership


def list_unread_totals(session: Session, *, actor: User) -> tuple[int, dict[str, int]]:
    counts = _unread_counts(session, tenant_id=actor.tenant_id, user_id=actor.id)
    return sum(counts.values()), {str(channel_id): count for channel_id, count in counts.items()}


def list_staff(session: Session, *, actor: User, search: str | None, limit: int) -> list[User]:
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
        statement = statement.where(or_(func.lower(User.full_name).like(pattern), func.lower(User.email).like(pattern)))
    return list(session.scalars(statement.order_by(User.full_name, User.id).limit(limit)).all())
