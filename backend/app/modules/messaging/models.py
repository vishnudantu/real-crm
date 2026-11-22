"""SQLAlchemy models for the tenant messaging trigger engine and outbox."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.tenancy import TenantOwned


class MessageChannel(StrEnum):
    WHATSAPP = "WHATSAPP"
    SMS = "SMS"
    EMAIL = "EMAIL"


class DeliveryStatus(StrEnum):
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


def utcnow() -> datetime:
    return datetime.now(UTC)


class MessageTemplate(TenantOwned, Base):
    """A tenant-owned outbound message body with merge tags, per channel/language."""

    __tablename__ = "message_templates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "name",
            "channel",
            "language",
            name="uq_message_templates_tenant_name_channel_language",
        ),
        Index("ix_message_templates_tenant_channel_language", "tenant_id", "channel", "language"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en", server_default="en")
    body: Mapped[str] = mapped_column(Text, nullable=False)
    provider_template_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    variables: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )


class TriggerRule(TenantOwned, Base):
    """Fires a template on a business event, optionally after a delay."""

    __tablename__ = "trigger_rules"
    __table_args__ = (
        Index("ix_trigger_rules_tenant_event_enabled", "tenant_id", "event", "enabled"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    template_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("message_templates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )


class MessageDelivery(TenantOwned, Base):
    """One outbound message; doubles as the transactional outbox row."""

    __tablename__ = "message_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_message_deliveries_tenant_idempotency",
        ),
        Index("ix_message_deliveries_status_next_attempt", "status", "next_attempt_at"),
        Index("ix_message_deliveries_tenant_created_at", "tenant_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    template_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("message_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trigger_rule_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("trigger_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    to_address: Mapped[str] = mapped_column(String(320), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="log", server_default="log")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DeliveryStatus.QUEUED.value,
        server_default=DeliveryStatus.QUEUED.value, index=True,
    )
    provider_msg_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    suppressed_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )
