"""PF-004: per-tenant Meta Lead Ads routing, verification, and consent."""

from __future__ import annotations

import hashlib
import hmac
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.security import hash_password
from app.modules.connectors.models import LeadIngestionEvent
from app.modules.integrations.models import IntegrationConnection
from app.modules.integrations.schemas import MetaPageConnectionUpsert
from app.modules.integrations.service import upsert_meta_page
from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD

pytest.importorskip("cryptography", reason="Integration credentials require cryptography.")


@pytest.fixture(autouse=True)
def vault_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptography.fernet import Fernet

    from app.core.config import get_settings

    monkeypatch.setattr(
        get_settings(), "encryption_key", Fernet.generate_key().decode(), raising=False
    )


def _fixture(session: Session, *, label: str = "one") -> tuple[Tenant, User, Project]:
    tenant = Tenant(slug=f"meta-{label}-{uuid4().hex[:8]}", name="Meta Customer")
    session.add(tenant)
    session.flush()
    role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one()
    admin = User(
        tenant_id=tenant.id,
        full_name="Meta Admin",
        email=f"meta.{tenant.id.hex[:8]}@example.com",
        password_hash=hash_password(TEST_PASSWORD),
        role_id=role.id,
        is_active=True,
    )
    session.add(admin)
    session.flush()
    project = Project(
        tenant_id=tenant.id,
        name="Meta Tower",
        slug=f"meta-{tenant.id.hex[:8]}",
        location="Hyderabad",
        status=ProjectStatus.ACTIVE.value,
        created_by=admin.id,
    )
    session.add(project)
    session.commit()
    return tenant, admin, project


def _connect(session: Session, admin: User, project: Project, page_id: str, *, active: bool = True):
    return upsert_meta_page(
        session,
        actor=admin,
        page_id=page_id,
        payload=MetaPageConnectionUpsert(
            project_id=project.id,
            access_token=f"token-{page_id}",
            app_secret=f"secret-{page_id}",
            webhook_verify_token=f"verify-{page_id}",
            is_active=active,
        ),
    )


def _payload(page_id: str, leadgen_id: str) -> dict:
    return {
        "object": "page",
        "entry": [{
            "id": page_id,
            "changes": [{
                "field": "leadgen",
                "value": {
                    "leadgen_id": leadgen_id,
                    "page_id": page_id,
                    "form_id": "form-100",
                    "ad_id": "ad-200",
                    "created_time": 1700000000,
                },
            }],
        }],
    }


def _signed(body: bytes, secret: str) -> dict[str, str]:
    return {"X-Hub-Signature-256": "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()}


def _post(client: TestClient, payload: dict, secret: str = "secret-page-1"):
    body = json.dumps(payload, separators=(",", ":")).encode()
    return client.post(
        "/api/v1/webhooks/meta", content=body,
        headers={**_signed(body, secret), "Content-Type": "application/json"},
    )


@pytest.fixture(autouse=True)
def graph_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fetch(leadgen_id: str, settings, access_token: str | None = None) -> dict:
        assert access_token == "token-page-1"
        return {"field_data": [
            {"name": "full_name", "values": ["Asha Meta"]},
            {"name": "email", "values": ["Asha.Meta@Example.com"]},
            {"name": "phone_number", "values": ["+91 98000 00123"]},
        ]}

    monkeypatch.setattr("app.modules.connectors.router.fetch_meta_lead", fetch)


def test_valid_signature_routes_to_page_tenant_and_project_with_consent_evidence(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, project = _fixture(session)
        _connect(session, admin, project, "page-1")
        other_tenant, other_admin, other_project = _fixture(session, label="two")
        _connect(session, other_admin, other_project, "page-other")

    response = _post(client, _payload("page-1", "lead-routed"))
    assert response.status_code == 200, response.text
    assert response.json() == {"processed": ["lead-routed"], "skipped": []}
    with test_session_factory() as session:
        lead = session.scalar(select(Lead).where(Lead.tenant_id == tenant.id))
        assert lead is not None
        assert lead.project_id == project.id
        assert lead.consent_to_contact is True
        assert session.scalar(select(Lead).where(Lead.tenant_id == other_tenant.id)) is None
        event = session.scalar(select(LeadIngestionEvent).where(LeadIngestionEvent.external_id == "lead-routed"))
        assert event.payload == {
            "source": "meta_lead_ads", "form_id": "form-100",
            "ad_id": "ad-200", "captured_at": 1700000000,
        }
        connection = session.scalar(select(IntegrationConnection).where(IntegrationConnection.external_account_id == "page-1"))
        assert connection.last_success_at is not None
        assert connection.last_error is None


def test_wrong_signature_rejects_whole_request_without_lead(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, project = _fixture(session)
        _connect(session, admin, project, "page-1")
    response = _post(client, _payload("page-1", "lead-forged"), secret="wrong-secret")
    assert response.status_code == 403
    with test_session_factory() as session:
        assert session.scalars(select(Lead)).all() == []


def test_unknown_page_is_skipped_without_fetching_or_creating_lead(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.modules.connectors.router.fetch_meta_lead",
        lambda *args, **kwargs: pytest.fail("Unknown pages must not access Graph API"),
    )
    response = _post(client, _payload("unknown-page", "lead-unknown"), secret="unused")
    assert response.status_code == 200
    assert response.json() == {"processed": [], "skipped": ["lead-unknown"]}
    with test_session_factory() as session:
        assert session.scalars(select(Lead)).all() == []


def test_same_phone_different_email_is_duplicate_under_or_semantics(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, project = _fixture(session)
        _connect(session, admin, project, "page-1")
        session.add(Lead(
            tenant_id=tenant.id, full_name="Existing Buyer",
            email="different@example.com", phone="+919800000123", project_id=project.id,
            source=LeadSource.WEBSITE.value, status=LeadStatus.NEW.value,
            consent_to_contact=True,
        ))
        session.commit()
    response = _post(client, _payload("page-1", "lead-duplicate"))
    assert response.status_code == 200
    assert response.json() == {"processed": [], "skipped": ["lead-duplicate"]}
    with test_session_factory() as session:
        assert len(session.scalars(select(Lead).where(Lead.tenant_id == tenant.id)).all()) == 1


def test_inactive_connection_is_skipped(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, project = _fixture(session)
        _connect(session, admin, project, "page-1", active=False)
    response = _post(client, _payload("page-1", "lead-inactive"))
    assert response.status_code == 200
    assert response.json() == {"processed": [], "skipped": ["lead-inactive"]}
    with test_session_factory() as session:
        assert session.scalars(select(Lead)).all() == []


def test_admin_connection_api_never_returns_secrets(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session], auth_headers,
) -> None:
    with test_session_factory() as session:
        tenant, admin, project = _fixture(session)
        email = admin.email
    headers = auth_headers(email, TEST_PASSWORD)
    payload = {
        "project_id": str(project.id), "access_token": "never-return-token",
        "app_secret": "never-return-secret", "webhook_verify_token": "never-return-verify",
    }
    response = client.put("/api/v1/integrations/meta/pages/page-admin", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    assert "never-return" not in response.text
    listed = client.get("/api/v1/integrations/connections", headers=headers)
    assert listed.status_code == 200
    assert "never-return" not in listed.text
    assert listed.json()[0]["external_account_id"] == "page-admin"
    assert client.delete("/api/v1/integrations/meta/pages/page-admin", headers=headers).status_code == 204


def test_processing_failure_records_redacted_error(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch,
) -> None:
    with test_session_factory() as session:
        _tenant, admin, project = _fixture(session)
        _connect(session, admin, project, "page-1")

    def fetch(leadgen_id: str, settings, access_token: str | None = None) -> dict:
        raise RuntimeError(
            f"Server error '500' for url 'https://graph.facebook.com/v21.0/{leadgen_id}"
            f"?access_token=leaked-page-token&fields=field_data'"
        )

    monkeypatch.setattr("app.modules.connectors.router.fetch_meta_lead", fetch)
    response = _post(client, _payload("page-1", "lead-failed"))
    assert response.status_code == 200
    assert response.json() == {"processed": [], "skipped": ["lead-failed"]}
    with test_session_factory() as session:
        connection = session.scalar(
            select(IntegrationConnection).where(IntegrationConnection.external_account_id == "page-1")
        )
        assert "leaked-page-token" not in (connection.last_error or "")
        assert "access_token=***" in (connection.last_error or "")
        assert connection.last_error_at is not None


def test_per_connection_and_global_subscription_handshakes(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch,
) -> None:
    with test_session_factory() as session:
        _tenant, admin, project = _fixture(session)
        _connect(session, admin, project, "page-1")
    from app.core.config import get_settings
    from pydantic import SecretStr

    monkeypatch.setattr(get_settings(), "meta_verify_token", SecretStr("global-verify"))
    for token in ("verify-page-1", "global-verify"):
        response = client.get(
            "/api/v1/webhooks/meta",
            params={"hub.mode": "subscribe", "hub.verify_token": token, "hub.challenge": "challenge-42"},
        )
        assert response.status_code == 200
        assert response.json() == "challenge-42"


def test_default_consent_basis_does_not_imply_contact_permission(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session],
) -> None:
    from app.modules.connectors.service import ingest_lead

    with test_session_factory() as session:
        tenant, _admin, project = _fixture(session)
        created = ingest_lead(
            session, tenant_id=tenant.id, project_id=project.id,
            full_name="Unspecified Consent", email="unspecified@example.com",
            phone=None, source=LeadSource.SOCIAL_MEDIA,
        )
        assert created.consent_to_contact is False
        assert created.opted_out is True
