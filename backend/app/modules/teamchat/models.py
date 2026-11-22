"""Tenant-scoped staff channels, memberships, and messages."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
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
from app.modules.users.models import User


class ChatChannelRole(StrEnum):
    """Membership roles within a staff channel."""

    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


def utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class ChatChannel(TenantOwned, Base):
    """An internal staff conversation channel within one tenant."""

    __tablename__ = "team_channels"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_team_channels_tenant_name"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_private: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
    )


class ChatChannelMember(TenantOwned, Base):
    """A staff user's membership in an internal channel."""

    __tablename__ = "team_channel_members"
    __table_args__ = (
        UniqueConstraint(
            "channel_id", "user_id", name="uq_team_channel_members_channel_user"
        ),
        CheckConstraint(
            "role IN ('ADMIN', 'MEMBER')", name="team_channel_member_role_valid"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    channel_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("team_channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ChatChannelRole.MEMBER.value,
        server_default=ChatChannelRole.MEMBER.value,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="joined")


class ChatMessage(TenantOwned, Base):
    """An individual staff message in an internal channel."""

    __tablename__ = "team_messages"
    __table_args__ = (
        CheckConstraint(
            "length(trim(body)) BETWEEN 1 AND 4000", name="team_message_body_valid"
        ),
        Index(
            "ix_team_messages_channel_id_created_at", "channel_id", "created_at"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    channel_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("team_channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
    )
    edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sender: Mapped[User | None] = relationship(
        foreign_keys=[sender_user_id], lazy="joined"
    )
