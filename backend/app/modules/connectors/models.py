"""Auditable raw lead-ingestion events (Meta, portal email, future providers)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.tenancy import TenantOwned


class LeadIngestionEvent(TenantOwned, Base):
    """A raw connector event retained for parsing forensics and idempotent replay."""

    __tablename__ = "lead_ingestion_events"
    __table_args__ = (
        Index("ix_lead_ingestion_provider_external", "provider", "external_id", unique=True),
        Index("ix_lead_ingestion_tenant_created_at", "tenant_id", "received_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC), server_default=func.now()
    )
