"""Pydantic contracts for per-tenant AI provider administration."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TenantAIProviderUpsert(BaseModel):
    """Register or replace this tenant's AI provider.

    ``api_key`` is accepted only over this write path; it is encrypted at rest
    and never echoed back — read paths return the masked last four characters.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: str = Field(min_length=2, max_length=64)
    api_key: str = Field(min_length=8, max_length=4096)
    model: str = Field(min_length=1, max_length=128)
    base_url: str | None = Field(default=None, max_length=500)


class TenantAIProviderResponse(BaseModel):
    """Masked provider configuration; ciphertext and raw keys never leave."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    base_url: str | None
    model: str
    is_active: bool
    api_key_masked: str
    created_at: datetime
    updated_at: datetime
