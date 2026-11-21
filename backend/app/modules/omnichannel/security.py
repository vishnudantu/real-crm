"""Encrypt per-tenant channel secrets and verify per-tenant webhook signatures.

Meta app secrets must never be shared across tenants: each tenant stores its
own encrypted credentials, and webhook verification uses that tenant's secret.

The vault derives a tenant-specific Fernet key from the global ``ENCRYPTION_KEY``
(or, in tests, an injected per-tenant key), so compromise of one tenant's
material does not expose any other tenant's credentials.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from app.core.config import get_settings
from app.modules.omnichannel.exceptions import ChannelConfigurationError

logger = logging.getLogger(__name__)

# Test-only override: set to a mapping of {tenant_id_hex: Fernet key}.
_TEST_TENANT_KEYS: dict[str, str] = {}


def _fernet_for_tenant(tenant_id) -> "object":
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:  # pragma: no cover - environment guard
        raise ChannelConfigurationError(
            "The 'cryptography' package is required to store channel credentials."
        ) from exc
    override = _TEST_TENANT_KEYS.get(str(tenant_id))
    if override:
        return Fernet(override.encode() if isinstance(override, str) else override)
    settings = get_settings()
    raw_key = getattr(settings, "encryption_key", None)
    secret = (
        raw_key.get_secret_value()
        if hasattr(raw_key, "get_secret_value")
        else raw_key
    )
    if not secret:
        raise ChannelConfigurationError(
            "ENCRYPTION_KEY is required to store encrypted channel credentials."
        )
    material = hashlib.sha256(f"{secret}|{tenant_id}".encode()).digest()
    import base64

    return Fernet(base64.urlsafe_b64encode(material))


def encrypt_credentials(credentials: dict, *, tenant_id) -> str:
    """Serialize and encrypt a credential mapping for at-rest storage."""

    plaintext = json.dumps(credentials, separators=(",", ":")).encode()
    return _fernet_for_tenant(tenant_id).encrypt(plaintext).decode()


def decrypt_credentials(ciphertext: str, *, tenant_id) -> dict:
    """Decrypt stored credentials; a failure means the key or data is invalid."""

    try:
        plaintext = _fernet_for_tenant(tenant_id).decrypt(ciphertext.encode())
        value = json.loads(plaintext)
    except ChannelConfigurationError:
        raise
    except Exception as exc:
        raise ChannelConfigurationError(
            "Stored channel credentials could not be decrypted."
        ) from exc
    if not isinstance(value, dict):
        raise ChannelConfigurationError("Stored channel credentials are malformed.")
    return value


def verify_hmac_sha256(*, raw_body: bytes, secret: str, signature_header: str) -> bool:
    """Verify an X-Hub-Signature-256 style header with constant-time comparison."""

    if not secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def hash_verify_token(token: str) -> str:
    """Store only a digest of a webhook verify token, never the token itself."""

    return hashlib.sha256(token.encode()).hexdigest()


def verify_subscription_token(*, mode: str | None, token: str | None, stored_hash: str | None) -> bool:
    """Compare a Meta hub.verify_token against the stored tenant-specific digest."""

    if mode != "subscribe" or not token or not stored_hash:
        return False
    return hmac.compare_digest(hash_verify_token(token), stored_hash)


def make_livekit_access_token(
    *,
    api_key: str,
    api_secret: str,
    room: str,
    identity: str,
    name: str | None = None,
    ttl_seconds: int = 3600,
    can_publish: bool = True,
    can_subscribe: bool = True,
) -> str:
    """Build a LiveKit-compatible participant JWT (HS256) without an SDK.

    The grant format mirrors LiveKit's access-token spec so the official JS
    client can join the room; a local LiveKit server validates the signature.
    """

    from datetime import UTC, datetime, timedelta

    import jwt

    now = datetime.now(UTC)
    claims = {
        "iss": api_key,
        "sub": identity,
        "nbf": int((now - timedelta(seconds=10)).timestamp()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
        "video": {
            "room": room,
            "roomJoin": True,
            "canPublish": can_publish,
            "canSubscribe": can_subscribe,
            "canPublishData": True,
        },
    }
    if name:
        claims["name"] = name
    return jwt.encode(claims, api_secret, algorithm="HS256")
