"""Operator tokens are cryptographically distinct from tenant access tokens."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import Settings, get_settings

OPERATOR_AUDIENCE = "propflow-operators"
OPERATOR_TOKEN_TYPE = "operator_access"


def create_operator_token(operator, *, settings: Settings | None = None) -> str:
    config = settings or get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(operator.id),
            "type": OPERATOR_TOKEN_TYPE,
            "operator_role": operator.role,
            "iat": now,
            "exp": now + timedelta(minutes=config.operator_token_expire_minutes),
            "iss": config.jwt_issuer,
            "aud": OPERATOR_AUDIENCE,
        },
        config.jwt_secret_key.get_secret_value(),
        algorithm=config.jwt_algorithm,
    )


def decode_operator_token(token: str, *, settings: Settings | None = None) -> UUID:
    config = settings or get_settings()
    payload = jwt.decode(
        token,
        config.jwt_secret_key.get_secret_value(),
        algorithms=[config.jwt_algorithm],
        audience=OPERATOR_AUDIENCE,
        issuer=config.jwt_issuer,
        options={"require": ["sub", "type", "iat", "exp", "iss", "aud"]},
    )
    if payload.get("type") != OPERATOR_TOKEN_TYPE:
        raise jwt.InvalidTokenError("Not an operator access token.")
    return UUID(str(payload["sub"]))
