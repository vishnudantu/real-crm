"""Global SaaS operator identity and platform-management audit records."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OperatorPermission(StrEnum):
    """Platform permissions can be granted independently of the operator role."""

    TENANTS_READ = "tenants.read"
    TENANTS_WRITE = "tenants.write"
    PLANS_WRITE = "plans.write"
    DEPLOYMENTS_WRITE = "deployments.write"
    OPERATORS_MANAGE = "operators.manage"
    AUDIT_READ = "audit.read"


ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "OWNER": frozenset(permission.value for permission in OperatorPermission),
    "SUPPORT": frozenset({OperatorPermission.TENANTS_READ.value, OperatorPermission.AUDIT_READ.value}),
    "SALES": frozenset({
        OperatorPermission.TENANTS_READ.value,
        OperatorPermission.TENANTS_WRITE.value,
        OperatorPermission.AUDIT_READ.value,
    }),
    "DEPLOYER": frozenset({
        OperatorPermission.TENANTS_READ.value,
        OperatorPermission.DEPLOYMENTS_WRITE.value,
    }),
}


def utcnow() -> datetime:
    return datetime.now(UTC)


class OperatorUser(Base):
    """A platform operator; intentionally has NO tenant_id or tenant role."""

    __tablename__ = "operator_users"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="OWNER")
    permissions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )

    def allowed(self, permission: OperatorPermission) -> bool:
        return permission.value in ROLE_PERMISSIONS.get(self.role, frozenset()) or permission.value in self.permissions


class OperatorAuditLog(Base):
    """Immutable audit trail for privileged platform-management actions."""

    __tablename__ = "operator_audit_logs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    operator_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("operator_users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_email: Mapped[str] = mapped_column(String(320), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(), index=True
    )
