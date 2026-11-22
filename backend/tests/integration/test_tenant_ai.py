"""Integration tests for per-tenant AI provider configuration (/tenant-ai).

Covers: encryption at rest, masked read-back (raw key never returned),
assistant resolution order (tenant override > central settings), fallback
when unset, clear, admin-only access, and cross-tenant isolation. No live
provider call is made anywhere; the HTTP client is fully mocked.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

pytest.importorskip(
    "cryptography", reason="Tenant AI provider keys require the cryptography package."
)

from app.modules.tenant_ai.models import TenantAIProvider  # noqa: E402
from app.modules.tenant_ai.schemas import TenantAIProviderUpsert  # noqa: E402
from app.modules.tenant_ai.service import (  # noqa: E402
    clear_provider,
    resolve_provider_config,
    set_provider,
)
from app.modules.users.models import RoleName  # noqa: E402

RAW_KEY = f"gsk_tenant_{uuid4().hex[:24]}"


@pytest.fixture(autouse=True)
def vault_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptography.fernet import Fernet

    from app.core.config import get_settings

    monkeypatch.setattr(
        get_settings(), "encryption_key", Fernet.generate_key().decode(), raising=False
    )


@pytest.fixture()
def env(
    client: TestClient,
    override_db: None,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> dict:
    admin = user_factory(role=RoleName.ADMIN)
    headers = auth_headers(admin.email)
    return {
        "factory": test_session_factory,
        "tenant_id": admin.tenant_id,
        "admin_id": admin.id,
        "admin_email": admin.email,
        "headers": headers,
    }


def _payload(provider: str = "groq", **overrides) -> dict:
    body = {"provider": provider, "api_key": RAW_KEY, "model": "llama-3.3-70b-versatile"}
    body.update(overrides)
    return body


class TestSetAndMask:
    def test_set_provider_encrypts_at_rest(self, env: dict) -> None:
        with env["factory"]() as s:
            from app.modules.users.models import User

            admin = s.get(User, env["admin_id"])
            record = set_provider(s, actor=admin, payload=TenantAIProviderUpsert(**_payload()))
            ciphertext = record.api_key_ciphertext
            assert ciphertext and ciphertext != RAW_KEY
            assert RAW_KEY not in ciphertext
            # Decrypt via the shared vault to confirm the round-trip.
            from app.modules.omnichannel.security import decrypt_credentials

            assert decrypt_credentials(ciphertext, tenant_id=env["tenant_id"]) == {"api_key": RAW_KEY}

    def test_only_one_active_per_tenant(self, env: dict) -> None:
        with env["factory"]() as s:
            from app.modules.users.models import User

            admin = s.get(User, env["admin_id"])
            set_provider(s, actor=admin, payload=TenantAIProviderUpsert(**_payload(model="m1")))
            set_provider(
                s,
                actor=admin,
                payload=TenantAIProviderUpsert(**_payload(model="m2", api_key=f"{RAW_KEY}x")),
            )
            active = s.scalars(
                select(TenantAIProvider).where(
                    TenantAIProvider.tenant_id == env["tenant_id"],
                    TenantAIProvider.is_active.is_(True),
                )
            ).all()
            assert len(active) == 1
            assert active[0].model == "m2"

    def test_get_returns_masked_last4_never_raw(
        self, client: TestClient, env: dict
    ) -> None:
        put = client.put("/api/v1/tenant-ai/provider", json=_payload(), headers=env["headers"])
        assert put.status_code == 200, put.text
        for body in (put.text, client.get("/api/v1/tenant-ai/provider", headers=env["headers"]).text):
            assert RAW_KEY not in body
            assert "ciphertext" not in body
        body = client.get("/api/v1/tenant-ai/provider", headers=env["headers"]).json()
        assert body["provider"] == "groq"
        assert body["model"] == "llama-3.3-70b-versatile"
        assert body["api_key_masked"].endswith(RAW_KEY[-4:])
        assert set(body["api_key_masked"]) == set(RAW_KEY[-4:]) | {"*"}
        assert body["is_active"] is True

    def test_openai_compatible_requires_base_url(self, client: TestClient, env: dict) -> None:
        r = client.put(
            "/api/v1/tenant-ai/provider",
            json=_payload(provider="openai_compatible"),
            headers=env["headers"],
        )
        assert r.status_code == 400

    def test_openai_compatible_accepts_base_url(self, client: TestClient, env: dict) -> None:
        r = client.put(
            "/api/v1/tenant-ai/provider",
            json=_payload(provider="openai_compatible", base_url="https://api.openai.com/v1"),
            headers=env["headers"],
        )
        assert r.status_code == 200, r.text
        assert r.json()["base_url"] == "https://api.openai.com/v1"


class TestResolveAndFallback:
    def test_resolve_returns_decrypted_config(self, env: dict) -> None:
        with env["factory"]() as s:
            from app.modules.users.models import User

            admin = s.get(User, env["admin_id"])
            set_provider(s, actor=admin, payload=TenantAIProviderUpsert(**_payload()))
            config = resolve_provider_config(s, tenant_id=env["tenant_id"])
            assert config is not None
            assert config == {
                "provider": "groq",
                "base_url": None,
                "api_key": RAW_KEY,
                "model": "llama-3.3-70b-versatile",
            }

    def test_resolve_none_when_unset_falls_back_to_central(self, env: dict) -> None:
        from app.modules.ai_assistant.provider import resolve_ai_client

        with env["factory"]() as s:
            assert resolve_provider_config(s, tenant_id=env["tenant_id"]) is None
        # Central fallback path is unchanged when no tenant provider is set.
        central = resolve_ai_client(tenant_config=None)
        assert central.__class__.__name__ == "GroqClient"

    def test_client_resolution_prefers_tenant_override(self) -> None:
        from app.modules.ai_assistant.client import GroqClient
        from app.modules.ai_assistant.provider import OpenAICompatibleClient, resolve_ai_client

        groq = resolve_ai_client(
            tenant_config={"provider": "groq", "base_url": None, "api_key": RAW_KEY, "model": "m-groq"}
        )
        assert isinstance(groq, GroqClient) and groq.api_key == RAW_KEY and groq.model == "m-groq"
        oai = resolve_ai_client(
            tenant_config={
                "provider": "openai_compatible",
                "base_url": "https://example.test/v1",
                "api_key": RAW_KEY,
                "model": "m-oai",
            }
        )
        assert isinstance(oai, OpenAICompatibleClient)
        assert oai.base_url == "https://example.test/v1" and oai.api_key == RAW_KEY and oai.model == "m-oai"

    def test_clear_provider(self, env: dict) -> None:
        with env["factory"]() as s:
            from app.modules.users.models import User

            admin = s.get(User, env["admin_id"])
            set_provider(s, actor=admin, payload=TenantAIProviderUpsert(**_payload()))
            clear_provider(s, tenant_id=env["tenant_id"])
            assert resolve_provider_config(s, tenant_id=env["tenant_id"]) is None


class TestAccessAndIsolation:
    @pytest.mark.parametrize("role", [RoleName.SALES_EXECUTIVE, RoleName.BUYER])
    def test_non_admin_403(self, client: TestClient, env: dict, user_factory, auth_headers, role) -> None:
        user = user_factory(role=role)
        headers = auth_headers(user.email)
        assert client.put("/api/v1/tenant-ai/provider", json=_payload(), headers=headers).status_code == 403
        assert client.get("/api/v1/tenant-ai/provider", headers=headers).status_code == 403
        assert client.delete("/api/v1/tenant-ai/provider", headers=headers).status_code == 403

    def test_cross_tenant_read_404(self, client: TestClient, env: dict, user_factory, auth_headers) -> None:
        # Configure provider in tenant A (the default env tenant).
        client.put("/api/v1/tenant-ai/provider", json=_payload(), headers=env["headers"])
        # A different tenant's admin sees 404, never tenant A's config.
        from app.modules.tenancy.models import Tenant

        with env["factory"]() as s:
            other = Tenant(slug=f"o-{uuid4().hex[:8]}", name="Other")
            s.add(other)
            s.commit()
        other_admin = user_factory(role=RoleName.ADMIN, tenant=other)
        other_headers = auth_headers(other_admin.email)
        assert client.get("/api/v1/tenant-ai/provider", headers=other_headers).status_code == 404
        # And resolve in tenant A still returns A's decrypted config (isolation).
        with env["factory"]() as s:
            config = resolve_provider_config(s, tenant_id=env["tenant_id"])
            assert config is not None and config["api_key"] == RAW_KEY
