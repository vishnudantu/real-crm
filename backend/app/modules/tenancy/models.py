"""Organization and white-label tenant configuration."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TenantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Tenant(Base):
    """An isolated organization using the shared PROPFLOW database."""

    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TenantStatus.ACTIVE.value, index=True
    )
    plan_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    theme_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="IN")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(UTC), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(UTC), server_default=func.now(),
        onupdate=lambda: datetime.now(UTC)
    )

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("brand_name", kwargs.get("name", ""))
        kwargs.setdefault("status", TenantStatus.ACTIVE.value)
        kwargs.setdefault("country", "IN")
        kwargs.setdefault("timezone", "UTC")
        kwargs.setdefault("currency", "INR")
        super().__init__(**kwargs)
