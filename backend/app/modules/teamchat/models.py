"""Private staff-only chat models, separate from buyer conversations."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.tenancy import TenantOwned


class TeamChannelKind(StrEnum):
    CHANNEL = "CHANNEL"
    DIRECT = "DIRECT"


class TeamChannelRole(StrEnum):
    OWNER = "OWNER"
    MODERATOR = "MODERATOR"
    MEMBER = "MEMBER"


def utcnow() -> datetime:
    return datetime.now(UTC)


class TeamChannel(TenantOwned, Base):
    """A staff-only channel or direct-message thread within one tenant."""

    __tablename__ = "team_channels"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_team_channels_tenant_name"),
        Index("ix_team_channels_tenant_kind", "tenant_id", "kind"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(500), nullable=True)
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TeamChannelKind.CHANNEL.value,
        server_default=TeamChannelKind.CHANNEL.value,
    )
    is_general: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_private: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )


class TeamChannelMember(TenantOwned, Base):
    """Membership and per-user read cursor; no separate read-state table."""

    __tablename__ = "team_channel_members"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "channel_id", "user_id",
            name="uq_team_channel_members_tenant_channel_user",
        ),
        CheckConstraint(
            "role IN ('OWNER','MODERATOR','MEMBER')", name="team_channel_member_role_valid"
        ),
        Index("ix_team_channel_members_user_channel", "tenant_id", "user_id", "channel_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    channel_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("team_channels.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TeamChannelRole.MEMBER.value,
        server_default=TeamChannelRole.MEMBER.value,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TeamMessage(TenantOwned, Base):
    """A plain-text staff message; mentions are validated user UUID strings."""

    __tablename__ = "team_messages"
    __table_args__ = (
        CheckConstraint(
            "length(trim(body)) BETWEEN 1 AND 4000", name="team_message_body_valid"
        ),
        Index(
            "ix_team_messages_tenant_channel_created",
            "tenant_id", "channel_id", "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    channel_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("team_channels.id", ondelete="CASCADE"), nullable=False
    )
    author_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    mentions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    author: Mapped["User | None"] = relationship(foreign_keys=[author_user_id], lazy="joined")


from app.modules.users.models import User
