"""Signed, purpose-bound OAuth state tokens for guided connection flows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt

from app.core.config import Settings, get_settings

OAUTH_AUDIENCE = "propflow-integration-oauth"
OAUTH_TOKEN_TYPE = "integration_oauth_state"
OAUTH_STATE_LIFETIME_MINUTES = 10


class OAuthStateError(ValueError):
    """An OAuth state is invalid, expired, or intended for another actor."""


@dataclass(frozen=True)
class OAuthStateClaims:
    tenant_id: UUID
    admin_user_id: UUID
    purpose: str


def create_oauth_state(
    *,
    tenant_id: UUID,
    admin_user_id: UUID,
    purpose: str,
    settings: Settings | None = None,
) -> str:
    """Bind an authorization redirect to one tenant, admin, and provider."""
    config = settings or get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(admin_user_id),
            "tenant_id": str(tenant_id),
            "purpose": purpose,
            "type": OAUTH_TOKEN_TYPE,
            "jti": str(uuid4()),
            "iat": now,
            "exp": now + timedelta(minutes=OAUTH_STATE_LIFETIME_MINUTES),
            "iss": config.jwt_issuer,
            "aud": OAUTH_AUDIENCE,
        },
        config.jwt_secret_key.get_secret_value(),
        algorithm=config.jwt_algorithm,
    )


def decode_oauth_state(
    token: str,
    *,
    tenant_id: UUID,
    admin_user_id: UUID,
    purpose: str,
    settings: Settings | None = None,
) -> OAuthStateClaims:
    """Validate a state and all of its authorization context, not just its signature."""
    config = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            config.jwt_secret_key.get_secret_value(),
            algorithms=[config.jwt_algorithm],
            issuer=config.jwt_issuer,
            audience=OAUTH_AUDIENCE,
            options={"require": ["sub", "tenant_id", "purpose", "type", "jti", "iat", "exp"]},
        )
        claims = OAuthStateClaims(
            tenant_id=UUID(str(payload["tenant_id"])),
            admin_user_id=UUID(str(payload["sub"])),
            purpose=str(payload["purpose"]),
        )
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
        raise OAuthStateError("The connection session is invalid or has expired. Start again.") from exc
    if (
        payload.get("type") != OAUTH_TOKEN_TYPE
        or claims.tenant_id != tenant_id
        or claims.admin_user_id != admin_user_id
        or claims.purpose != purpose
    ):
        raise OAuthStateError("The connection session does not match this account. Start again.")
    return claims
