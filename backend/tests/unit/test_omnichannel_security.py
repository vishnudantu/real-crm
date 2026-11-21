"""Unit tests for the encrypted credential vault and LiveKit token format."""

from __future__ import annotations

import jwt
import pytest

from app.modules.omnichannel.exceptions import ChannelConfigurationError
from app.modules.omnichannel.security import make_livekit_access_token

requires_cryptography = pytest.importorskip(
    "cryptography", reason="Install 'cryptography' to test the credential vault."
)


@pytest.fixture()
def vault_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptography.fernet import Fernet

    from app.core.config import get_settings

    monkeypatch.setattr(
        get_settings(), "encryption_key", Fernet.generate_key().decode(), raising=False
    )


class TestCredentialVault:
    def test_roundtrip(self, vault_key: None) -> None:
        from app.modules.omnichannel.security import decrypt_credentials, encrypt_credentials

        payload = {"access_token": "EAQD...", "app_secret": "s3cr3t"}
        ciphertext = encrypt_credentials(payload, tenant_id="tenant-1")
        assert "EAQD" not in ciphertext
        assert decrypt_credentials(ciphertext, tenant_id="tenant-1") == payload

    def test_ciphertext_is_randomised(self, vault_key: None) -> None:
        from app.modules.omnichannel.security import encrypt_credentials

        payload = {"a": "1"}
        assert encrypt_credentials(payload, tenant_id="tenant-1") != encrypt_credentials(
            payload, tenant_id="tenant-1"
        )

    def test_tampered_ciphertext_raises(self, vault_key: None) -> None:
        from app.modules.omnichannel.security import decrypt_credentials, encrypt_credentials

        ciphertext = encrypt_credentials({"a": "1"}, tenant_id="tenant-1")
        with pytest.raises(ChannelConfigurationError):
            decrypt_credentials(ciphertext[:-4] + "AAAA", tenant_id="tenant-1")

    def test_missing_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.core.config import get_settings
        from app.modules.omnichannel.security import encrypt_credentials

        monkeypatch.setattr(get_settings(), "encryption_key", None, raising=False)
        with pytest.raises(ChannelConfigurationError, match="ENCRYPTION_KEY"):
            encrypt_credentials({"a": "1"}, tenant_id="tenant-1")

    def test_cross_tenant_decryption_fails(self, vault_key: None) -> None:
        from app.modules.omnichannel.security import decrypt_credentials, encrypt_credentials

        ciphertext = encrypt_credentials({"secret": "x"}, tenant_id="tenant-A")
        with pytest.raises(ChannelConfigurationError):
            decrypt_credentials(ciphertext, tenant_id="tenant-B")


class TestLiveKitToken:
    def test_token_carries_video_grants(self) -> None:
        token = make_livekit_access_token(
            api_key="AP1234567890abcdef",
            api_secret="c" * 32,
            room="tenant-1-call-abc",
            identity="agent-1",
            name="Priya Sharma",
            ttl_seconds=900,
        )
        claims = jwt.decode(
            token, "c" * 32, algorithms=["HS256"], leeway=60, options={"verify_aud": False}
        )
        assert claims["iss"] == "AP1234567890abcdef"
        assert claims["sub"] == "agent-1"
        assert claims["video"]["room"] == "tenant-1-call-abc"
        assert claims["video"]["roomJoin"] is True
        assert claims["video"]["canPublish"] is True

    def test_wrong_secret_rejected(self) -> None:
        token = make_livekit_access_token(
            api_key="AP1", api_secret="a" * 32, room="r", identity="i"
        )
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(token, "wrong-secret", algorithms=["HS256"], options={"verify_aud": False})
