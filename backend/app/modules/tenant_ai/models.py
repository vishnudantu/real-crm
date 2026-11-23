"""Tenant-owned AI provider configuration with encrypted API keys.

``api_key_ciphertext`` holds a Fernet-encrypted JSON object produced by the
shared omnichannel credential vault (per-tenant derived key). The raw key is
never stored or returned; API responses carry only the masked last four
characters.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.tenancy import TenantOwned

PROVIDER_GROQ = "groq"
PROVIDER_OPENAI_COMPATIBLE = "openai_compatible"


def utcnow() -> datetime:
    return datetime.now(UTC)


class TenantAIProvider(TenantOwned, Base):
    """A tenant's own chat provider selection; at most one active per tenant."""

    __tablename__ = "tenant_ai_providers"
    __table_args__ = (
        Index(
            "uq_tenant_ai_providers_active_tenant",
            "tenant_id",
            unique=True,
            sqlite_where=text("is_active"),
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    api_key_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(), onupdate=utcnow
    )
