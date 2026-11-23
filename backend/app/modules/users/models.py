"""SQLAlchemy models for roles and users."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    false,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base
from app.db.tenancy import TenantOwned


class RoleName(StrEnum):
    """Built-in application roles."""

    BUYER = "BUYER"
    SALES_EXECUTIVE = "SALES_EXECUTIVE"
    MANAGER = "MANAGER"
    ADMIN = "ADMIN"


def utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class Role(Base):
    """A role that grants a user a set of application capabilities."""

    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(
        String(32), nullable=False, unique=True, index=True
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )

    users: Mapped[list["User"]] = relationship(back_populates="role")

    @validates("name")
    def _normalize_name(self, _key: str, value: str) -> str:
        return value.strip().upper()


class CustomRole(TenantOwned, Base):
    """A tenant-defined permission set for staff authentication."""

    __tablename__ = "custom_roles"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "name", name="uq_custom_roles_tenant_id_name"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    permissions: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    is_builtin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", use_alter=True),
        nullable=False,
        index=True,
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

    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    users: Mapped[list["User"]] = relationship(
        back_populates="custom_role",
        foreign_keys="User.custom_role_id",
    )

    @validates("name")
    def _normalize_name(self, _key: str, value: str) -> str:
        return value.strip()

    @validates("permissions")
    def _validate_permissions(self, _key: str, value: list[str]) -> list[str]:
        from app.modules.users.permissions import validate_permissions

        return validate_permissions(value)


class User(TenantOwned, Base):
    """A PropFlow account.

    Passwords are represented only by an Argon2 hash. Email addresses are
    normalized to lowercase before they reach the database layer.
    """

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_tenant_id_id", "tenant_id", "id"),
    )

    security_version: Mapped[int] = mapped_column(nullable=False, default=1, server_default="1")

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(
        String(320), nullable=False, unique=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    role_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    custom_role_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("custom_roles.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
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

    role: Mapped[Role] = relationship(back_populates="users", lazy="joined")
    custom_role: Mapped[CustomRole | None] = relationship(
        back_populates="users", foreign_keys=[custom_role_id], lazy="joined"
    )

    @property
    def permission_keys(self) -> frozenset[str]:
        """Permissions resolved from the tenant role on every request."""

        return (
            frozenset(self.custom_role.permissions or [])
            if self.custom_role
            else frozenset()
        )

    @validates("email")
    def _normalize_email(self, _key: str, value: str) -> str:
        return value.strip().lower()
