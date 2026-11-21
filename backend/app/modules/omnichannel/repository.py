"""Tenant-scoped queries for channel credentials, threads, and calls."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.modules.omnichannel.models import (
    CallRecord,
    CallRecording,
    ChannelConversation,
    ChannelCredential,
    ChannelMessage,
)


def get_credential(session: Session, *, tenant_id: UUID, channel: str) -> ChannelCredential | None:
    return session.scalar(
        select(ChannelCredential).where(
            ChannelCredential.tenant_id == tenant_id,
            ChannelCredential.channel == channel,
            ChannelCredential.is_active.is_(True),
        )
    )


def list_credentials(session: Session, *, tenant_id: UUID) -> list[ChannelCredential]:
    return list(
        session.scalars(
            select(ChannelCredential)
            .where(ChannelCredential.tenant_id == tenant_id)
            .order_by(ChannelCredential.channel)
        ).all()
    )


def get_conversation(
    session: Session, *, tenant_id: UUID, conversation_id: UUID, with_messages: bool = False
) -> ChannelConversation | None:
    statement = select(ChannelConversation).where(
        ChannelConversation.tenant_id == tenant_id,
        ChannelConversation.id == conversation_id,
    )
    if with_messages:
        statement = statement.options(selectinload(ChannelConversation.messages))
    return session.scalar(statement)


def find_thread(
    session: Session, *, tenant_id: UUID, channel: str, external_thread_id: str
) -> ChannelConversation | None:
    return session.scalar(
        select(ChannelConversation).where(
            ChannelConversation.tenant_id == tenant_id,
            ChannelConversation.channel == channel,
            ChannelConversation.external_thread_id == external_thread_id,
        )
    )


def find_message_by_external_id(
    session: Session, *, tenant_id: UUID, channel: str, external_message_id: str
) -> ChannelMessage | None:
    return session.scalar(
        select(ChannelMessage).where(
            ChannelMessage.tenant_id == tenant_id,
            ChannelMessage.channel == channel,
            ChannelMessage.external_message_id == external_message_id,
        )
    )


def list_inbox(
    session: Session,
    *,
    tenant_id: UUID,
    channel: str | None = None,
    assigned_to_id: UUID | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ChannelConversation], int, int]:
    filters = [ChannelConversation.tenant_id == tenant_id]
    if channel:
        filters.append(ChannelConversation.channel == channel)
    if assigned_to_id:
        filters.append(ChannelConversation.assigned_to_id == assigned_to_id)
    if status:
        filters.append(ChannelConversation.status == status)
    statement = select(ChannelConversation).where(*filters)
    total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    unread_total = session.scalar(
        select(func.coalesce(func.sum(ChannelConversation.unread_count), 0)).where(*filters)
    ) or 0
    items = list(
        session.scalars(
            statement.order_by(ChannelConversation.last_message_at.desc().nulls_last())
            .limit(limit)
            .offset(offset)
        ).all()
    )
    return items, int(total), int(unread_total)


def get_call(session: Session, *, tenant_id: UUID, call_id: UUID) -> CallRecord | None:
    return session.scalar(
        select(CallRecord)
        .where(CallRecord.tenant_id == tenant_id, CallRecord.id == call_id)
        .options(selectinload(CallRecord.recordings))
    )


def get_call_by_room(session: Session, *, tenant_id: UUID, room_name: str) -> CallRecord | None:
    return session.scalar(
        select(CallRecord).where(
            CallRecord.tenant_id == tenant_id, CallRecord.room_name == room_name
        )
    )


def list_recordings(session: Session, *, tenant_id: UUID, call_id: UUID) -> list[CallRecording]:
    return list(
        session.scalars(
            select(CallRecording).where(
                CallRecording.tenant_id == tenant_id, CallRecording.call_id == call_id
            )
        ).all()
    )
