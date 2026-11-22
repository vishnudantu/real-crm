"""Tenant-scoped database queries for internal staff chat."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.modules.teamchat.models import ChatChannel, ChatChannelMember, ChatMessage


def get_channel_by_id(
    session: Session, channel_id: UUID, *, tenant_id: UUID
) -> ChatChannel | None:
    """Return a channel only within the caller's tenant."""

    return session.scalar(
        select(ChatChannel).where(
            ChatChannel.id == channel_id, ChatChannel.tenant_id == tenant_id
        )
    )


def get_channel_by_name(
    session: Session, *, tenant_id: UUID, name: str
) -> ChatChannel | None:
    """Return a channel with the given name within one tenant."""

    return session.scalar(
        select(ChatChannel).where(
            ChatChannel.tenant_id == tenant_id, ChatChannel.name == name
        )
    )


def get_membership(
    session: Session, *, tenant_id: UUID, channel_id: UUID, user_id: UUID
) -> ChatChannelMember | None:
    """Return the user's membership in a tenant-scoped channel."""

    return session.scalar(
        select(ChatChannelMember)
        .options(joinedload(ChatChannelMember.user))
        .where(
            ChatChannelMember.tenant_id == tenant_id,
            ChatChannelMember.channel_id == channel_id,
            ChatChannelMember.user_id == user_id,
        )
    )


def list_visible_channels(
    session: Session, *, tenant_id: UUID, user_id: UUID
) -> list[ChatChannel]:
    """Return public channels plus channels the user has joined."""

    return list(
        session.scalars(
            select(ChatChannel)
            .where(
                ChatChannel.tenant_id == tenant_id,
                or_(
                    ChatChannel.is_private.is_(False),
                    select(ChatChannelMember.id)
                    .where(
                        ChatChannelMember.tenant_id == tenant_id,
                        ChatChannelMember.channel_id == ChatChannel.id,
                        ChatChannelMember.user_id == user_id,
                    )
                    .exists(),
                ),
            )
            .order_by(ChatChannel.created_at, ChatChannel.id)
        ).all()
    )


def member_count_map(session: Session, *, tenant_id: UUID) -> dict[UUID, int]:
    """Count members for all channels in one tenant."""

    rows = session.execute(
        select(ChatChannelMember.channel_id, func.count(ChatChannelMember.id))
        .where(ChatChannelMember.tenant_id == tenant_id)
        .group_by(ChatChannelMember.channel_id)
    ).all()
    return {channel_id: int(count) for channel_id, count in rows}


def list_members(
    session: Session, *, tenant_id: UUID, channel_id: UUID
) -> list[ChatChannelMember]:
    """Return memberships with their staff identities."""

    return list(
        session.scalars(
            select(ChatChannelMember)
            .options(joinedload(ChatChannelMember.user))
            .where(
                ChatChannelMember.tenant_id == tenant_id,
                ChatChannelMember.channel_id == channel_id,
            )
            .order_by(ChatChannelMember.joined_at, ChatChannelMember.id)
        ).all()
    )


def get_message_by_id(
    session: Session, message_id: UUID, *, tenant_id: UUID
) -> ChatMessage | None:
    """Return a message only within the caller's tenant."""

    return session.scalar(
        select(ChatMessage)
        .options(joinedload(ChatMessage.sender))
        .where(ChatMessage.id == message_id, ChatMessage.tenant_id == tenant_id)
    )


def count_messages(
    session: Session, *, tenant_id: UUID, channel_id: UUID
) -> int:
    """Count messages for pagination."""

    return session.scalar(
        select(func.count())
        .select_from(ChatMessage)
        .where(
            ChatMessage.tenant_id == tenant_id,
            ChatMessage.channel_id == channel_id,
        )
    ) or 0


def list_messages(
    session: Session,
    *,
    tenant_id: UUID,
    channel_id: UUID,
    offset: int = 0,
    limit: int,
    cursor: tuple[datetime, UUID] | None = None,
) -> list[ChatMessage]:
    """Return a bounded, stable, newest-first message page."""

    conditions = [
        ChatMessage.tenant_id == tenant_id,
        ChatMessage.channel_id == channel_id,
    ]
    if cursor is not None:
        timestamp, identifier = cursor
        conditions.append(
            or_(
                ChatMessage.created_at < timestamp,
                and_(
                    ChatMessage.created_at == timestamp,
                    ChatMessage.id < identifier,
                ),
            )
        )
    return list(
        session.scalars(
            select(ChatMessage)
            .options(joinedload(ChatMessage.sender))
            .where(*conditions)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
    )
