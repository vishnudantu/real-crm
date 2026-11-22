"""Tenant-owned external integration connections and encrypted credentials."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.tenancy import TenantOwned


def utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(UTC)


class IntegrationConnection(TenantOwned, Base):
    """A provider account whose page id uniquely identifies its owner."""

    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint("external_account_id", name="uq_integration_connections_external_account"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_account_id: Mapped[str] = mapped_column(String(128), nullable=False)
    project_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    credentials_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    connection_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )
    pending_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    webhook_verify_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(), onupdate=utcnow
    )
