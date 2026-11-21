"""Operator-managed tenant deployment tracking (never an implicit live deploy)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.tenancy import TenantOwned


class DeploymentStatus(StrEnum):
    REQUESTED = "REQUESTED"
    PROVISIONING = "PROVISIONING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Deployment(TenantOwned, Base):
    """An auditable deployment request for an operator to execute via the provider."""

    __tablename__ = "tenant_deployments"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    environment: Mapped[str] = mapped_column(String(64), nullable=False)
    region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=DeploymentStatus.REQUESTED.value)
    deployment_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    repository_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("operator_users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
    )
