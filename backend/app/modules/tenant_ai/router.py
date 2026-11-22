"""Admin endpoints for the tenant's own AI provider configuration.

The raw API key is accepted once (PUT), stored encrypted, and never returned;
reads expose only the masked last four characters.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser
from app.modules.tenant_ai.schemas import (
    TenantAIProviderResponse,
    TenantAIProviderUpsert,
)
from app.modules.tenant_ai.service import (
    clear_provider,
    get_provider_masked,
    set_provider,
)

router = APIRouter(prefix="/tenant-ai", tags=["tenant-ai"])


@router.put("/provider", response_model=TenantAIProviderResponse)
def configure_provider(
    payload: TenantAIProviderUpsert,
    db: Annotated[Session, Depends(get_db)],
    actor: AdminUser,
) -> dict:
    """Store this organization's AI provider and encrypted key (admin only).

    Returns only the masked configuration; the raw key is never echoed back.
    """

    set_provider(db, actor=actor, payload=payload)
    return get_provider_masked(db, tenant_id=actor.tenant_id)


@router.get("/provider", response_model=TenantAIProviderResponse)
def read_provider(
    db: Annotated[Session, Depends(get_db)],
    actor: AdminUser,
) -> dict:
    """Return the active provider with only the masked key tail (admin only)."""

    return get_provider_masked(db, tenant_id=actor.tenant_id)


@router.delete("/provider", status_code=status.HTTP_204_NO_CONTENT)
def remove_provider(
    db: Annotated[Session, Depends(get_db)],
    actor: AdminUser,
) -> None:
    """Clear this organization's provider; assistant falls back to central settings."""

    clear_provider(db, tenant_id=actor.tenant_id)
