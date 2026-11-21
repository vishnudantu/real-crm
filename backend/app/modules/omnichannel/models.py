"""Tenant-owned omnichannel threads, messages, calls, and encrypted credentials."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.tenancy import TenantOwned


def utcnow() -> datetime:
    return datetime.now(UTC)


def _quoted(values: type[StrEnum]) -> str:
    return ", ".join(f"'{v.value}'" for v in values)


class ChannelType(StrEnum):
    """Supported external messaging channels plus the native web chat."""

    WEB_CHAT = "WEB_CHAT"
    WHATSAPP = "WHATSAPP"
    INSTAGRAM = "INSTAGRAM"
    MESSENGER = "MESSENGER"
    SMS = "SMS"
    EMAIL = "EMAIL"
    VOICE = "VOICE"


class MessageDirection(StrEnum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class CallDirection(StrEnum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class CallStatus(StrEnum):
    INITIATED = "INITIATED"
    RINGING = "RINGING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    MISSED = "MISSED"
    BUSY = "BUSY"


class RecordingStatus(StrEnum):
    PENDING = "PENDING"
    RECORDING = "RECORDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ChannelCredential(TenantOwned, Base):
    """Encrypted per-tenant channel configuration.

    ``credentials_ciphertext`` holds a Fernet-encrypted JSON object. The
    ``config`` column carries only non-secret routing identifiers.
    """

    __tablename__ = "channel_credentials"
    __table_args__ = (
        UniqueConstraint("tenant_id", "channel", name="uq_channel_credentials_tenant_channel"),
        CheckConstraint(f"channel IN ({_quoted(ChannelType)})", name="ck_channel_credentials_channel"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    credentials_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    webhook_verify_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(), onupdate=utcnow
    )


class ChannelConversation(TenantOwned, Base):
    """A unified thread for one contact on one channel."""

    __tablename__ = "channel_conversations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "channel", "external_thread_id", name="uq_channel_conversations_thread"
        ),
        Index("ix_channel_conversations_tenant_updated", "tenant_id", "updated_at"),
        Index("ix_channel_conversations_tenant_unread", "tenant_id", "unread_count"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_to_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_thread_id: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="OPEN", index=True)
    last_message_preview: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unread_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(), onupdate=utcnow
    )

    messages: Mapped[list["ChannelMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="ChannelMessage.created_at"
    )


class ChannelMessage(TenantOwned, Base):
    """A single inbound or outbound channel message, idempotent by provider id."""

    __tablename__ = "channel_messages"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "channel", "external_message_id", name="uq_channel_messages_external_id"
        ),
        Index("ix_channel_messages_conversation_created", "conversation_id", "created_at"),
        CheckConstraint(
            f"direction IN ({_quoted(MessageDirection)})", name="ck_channel_messages_direction"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("channel_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default="TEXT")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="RECEIVED", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(), index=True
    )

    conversation: Mapped[ChannelConversation] = relationship(back_populates="messages")


class CallRecord(TenantOwned, Base):
    """A browser or phone call session backed by a LiveKit room."""

    __tablename__ = "call_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "room_name", name="uq_call_records_room"),
        CheckConstraint(f"direction IN ({_quoted(CallDirection)})", name="ck_call_records_direction"),
        CheckConstraint(f"status IN ({_quoted(CallStatus)})", name="ck_call_records_status"),
        Index("ix_call_records_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("channel_conversations.id", ondelete="SET NULL"), nullable=True
    )
    agent_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=CallStatus.INITIATED.value)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    room_name: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str | None] = mapped_column(String(255), nullable=True)
    caller_identity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(), onupdate=utcnow
    )

    recordings: Mapped[list["CallRecording"]] = relationship(
        back_populates="call", cascade="all, delete-orphan"
    )


class CallRecording(TenantOwned, Base):
    """A recording artifact produced by LiveKit Egress or a simulated provider."""

    __tablename__ = "call_recordings"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_quoted(RecordingStatus)})", name="ck_call_recordings_status"
        ),
        CheckConstraint("size_bytes >= 0", name="ck_call_recordings_size_non_negative"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    call_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("call_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    egress_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default=RecordingStatus.PENDING.value)
    storage_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="audio/ogg")
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    call: Mapped[CallRecord] = relationship(back_populates="recordings")
