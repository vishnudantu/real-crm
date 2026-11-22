"""Business logic for per-tenant AI provider configuration.

Secrets reuse the omnichannel credential vault (``encrypt_credentials`` /
``decrypt_credentials``): a tenant-specific Fernet key derived from the global
``ENCRYPTION_KEY``, so a raw API key is never stored or returned. The vault's
encrypted blob holds a JSON object ``{"api_key": ...}``.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.omnichannel.exceptions import ChannelConfigurationError
from app.modules.omnichannel.security import decrypt_credentials, encrypt_credentials
from app.modules.tenant_ai.exceptions import TenantAIProviderConfigurationError
from app.modules.tenant_ai.models import PROVIDER_GROQ, PROVIDER_OPENAI_COMPATIBLE, TenantAIProvider
from app.modules.tenant_ai.schemas import TenantAIProviderUpsert
from app.modules.users.models import User

logger = logging.getLogger("propflow.tenant_ai.service")

_MASK_VISIBLE_TAIL = 4
_VALID_PROVIDERS = frozenset({PROVIDER_GROQ, PROVIDER_OPENAI_COMPATIBLE})


def _validate(payload: TenantAIProviderUpsert) -> None:
    if payload.provider not in _VALID_PROVIDERS:
        raise TenantAIProviderConfigurationError(
            f"Unsupported provider '{payload.provider}'. "
            f"Choose one of: {', '.join(sorted(_VALID_PROVIDERS))}."
        )
    if payload.provider == PROVIDER_OPENAI_COMPATIBLE and not (payload.base_url or "").strip():
        raise TenantAIProviderConfigurationError(
            "base_url is required for an OpenAI-compatible provider."
        )
    if payload.provider == PROVIDER_GROQ and payload.base_url:
        raise TenantAIProviderConfigurationError(
            "base_url must be empty for the built-in 'groq' provider."
        )


def mask_api_key(api_key: str) -> str:
    """Return a display-safe mask showing only the final four characters."""

    if len(api_key) <= _MASK_VISIBLE_TAIL:
        return "*" * len(api_key)
    return f"{'*' * 6}{api_key[-_MASK_VISIBLE_TAIL:]}"


def set_provider(
    session: Session, *, actor: User, payload: TenantAIProviderUpsert
) -> TenantAIProvider:
    """Encrypt and store the tenant's active provider, deactivating any prior one."""

    _validate(payload)
    ciphertext = encrypt_credentials({"api_key": payload.api_key}, tenant_id=actor.tenant_id)

    # Only one active provider per tenant: demote existing rows first, then
    # insert (or reactivate) exactly one active row.
    session.execute(
        update(TenantAIProvider)
        .where(
            TenantAIProvider.tenant_id == actor.tenant_id,
            TenantAIProvider.is_active.is_(True),
        )
        .values(is_active=False)
    )
    record = TenantAIProvider(
        tenant_id=actor.tenant_id,
        provider=payload.provider,
        base_url=payload.base_url,
        api_key_ciphertext=ciphertext,
        model=payload.model,
        is_active=True,
        created_by=actor.id,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    logger.info(
        "Tenant AI provider set", extra={"tenant_id": str(actor.tenant_id), "provider": record.provider}
    )
    return record


def get_active(session: Session, *, tenant_id: UUID) -> TenantAIProvider | None:
    """Return the tenant's active provider row, or None when unset."""

    return session.scalar(
        select(TenantAIProvider)
        .where(
            TenantAIProvider.tenant_id == tenant_id,
            TenantAIProvider.is_active.is_(True),
        )
        .order_by(TenantAIProvider.updated_at.desc())
    )


def get_provider_masked(session: Session, *, tenant_id: UUID) -> dict:
    """Return the active provider with the API key masked to its last four characters.

    Never returns the raw key or the ciphertext.
    """

    record = get_active(session, tenant_id=tenant_id)
    if record is None:
        from app.modules.tenant_ai.exceptions import TenantAIProviderNotFoundError

        raise TenantAIProviderNotFoundError()
    credentials = _decrypt(record.api_key_ciphertext, tenant_id)
    return {
        "id": record.id,
        "provider": record.provider,
        "base_url": record.base_url,
        "model": record.model,
        "is_active": record.is_active,
        "api_key_masked": mask_api_key(credentials.get("api_key", "")),
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def clear_provider(session: Session, *, tenant_id: UUID) -> None:
    """Remove every stored provider row for the tenant (hard delete)."""

    session.execute(
        TenantAIProvider.__table__.delete().where(
            TenantAIProvider.tenant_id == tenant_id
        )
    )
    session.commit()


def resolve_provider_config(session: Session, *, tenant_id: UUID) -> dict | None:
    """Return the decrypted runtime config for assistant calls, or None.

    ``None`` means the tenant has no active provider and the caller must fall
    back to the central (environment) AI settings.
    """

    record = get_active(session, tenant_id=tenant_id)
    if record is None:
        return None
    try:
        credentials = _decrypt(record.api_key_ciphertext, tenant_id)
    except ChannelConfigurationError:
        logger.warning(
            "Tenant AI provider credentials unreadable; falling back to central settings",
            extra={"tenant_id": str(tenant_id)},
        )
        return None
    api_key = (credentials.get("api_key") or "").strip()
    if not api_key:
        return None
    return {
        "provider": record.provider,
        "base_url": record.base_url,
        "api_key": api_key,
        "model": record.model,
    }


def _decrypt(ciphertext: str, tenant_id: UUID) -> dict:
    try:
        return decrypt_credentials(ciphertext, tenant_id=tenant_id)
    except ChannelConfigurationError as exc:
        raise TenantAIProviderConfigurationError(
            "Stored provider credentials could not be decrypted."
        ) from exc
