"""Guided Meta/Google connection flows: state JWTs, redirects, exchanges, finalize."""

from __future__ import annotations

import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.security import hash_password
from app.modules.integrations.connection_service import get_owned_connection
from app.modules.integrations.models import IntegrationConnection
from app.modules.integrations.oauth_state import (
    OAuthStateError,
    create_oauth_state,
    decode_oauth_state,
)
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD

pytest.importorskip("cryptography", reason="Connection credentials require cryptography.")

META_FIELDS = {
    "meta_oauth_client_id": "meta-app-123",
    "meta_oauth_client_secret": SecretStr("meta-app-secret"),
    "oauth_redirect_base_url": "https://app.propflow.test",
}
GOOGLE_FIELDS = {
    "google_ads_developer_token": SecretStr("dev-token"),
    "google_ads_client_id": "google-client.apps.googleusercontent.com",
    "google_ads_client_secret": SecretStr("google-client-secret"),
    "oauth_redirect_base_url": "https://app.propflow.test",
}


@pytest.fixture(autouse=True)
def vault_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptography.fernet import Fernet

    from app.core.config import get_settings

    monkeypatch.setattr(
        get_settings(), "encryption_key", Fernet.generate_key().decode(), raising=False
    )


def _configure(monkeypatch: pytest.MonkeyPatch, fields: dict[str, object]) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    for name, value in fields.items():
        monkeypatch.setattr(settings, name, value, raising=False)


def _fixture(session: Session, *, label: str) -> tuple[Tenant, User, Project]:
    tenant = Tenant(slug=f"connect-{label}-{uuid.uuid4().hex[:8]}", name="Connect Co")
    session.add(tenant)
    session.flush()
    role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one()
    admin = User(
        tenant_id=tenant.id,
        full_name="Connect Admin",
        email=f"connect.{label}.{tenant.id.hex[:8]}@example.com",
        password_hash=hash_password(TEST_PASSWORD),
        role_id=role.id,
        is_active=True,
    )
    session.add(admin)
    session.flush()
    project = Project(
        tenant_id=tenant.id,
        name="Connect Tower",
        slug=f"connect-{label}-{tenant.id.hex[:8]}",
        location="Hyderabad",
        status=ProjectStatus.ACTIVE.value,
        created_by=admin.id,
    )
    session.add(project)
    session.commit()
    return tenant, admin, project


# ---------------------------------------------------------------------------
# State JWT unit tests
# ---------------------------------------------------------------------------


def test_state_roundtrip_and_wrong_tenant_rejected() -> None:
    tenant_a, admin_a = uuid.uuid4(), uuid.uuid4()
    state = create_oauth_state(
        tenant_id=tenant_a,
        admin_user_id=admin_a,
        purpose="meta_lead_ads_connect",
    )
    claims = decode_oauth_state(
        state, tenant_id=tenant_a, admin_user_id=admin_a, purpose="meta_lead_ads_connect"
    )
    assert claims.tenant_id == tenant_a
    assert claims.admin_user_id == admin_a
    with pytest.raises(OAuthStateError):
        decode_oauth_state(
            state,
            tenant_id=uuid.uuid4(),
            admin_user_id=admin_a,
            purpose="meta_lead_ads_connect",
        )
    with pytest.raises(OAuthStateError):
        decode_oauth_state(
            state,
            tenant_id=tenant_a,
            admin_user_id=admin_a,
            purpose="google_ads_connect",
        )
    forged = jwt.encode(
        {
            "sub": str(admin_a),
            "tenant_id": str(tenant_a),
            "purpose": "meta_lead_ads_connect",
            "type": "integration_oauth_state",
            "jti": "x",
            "aud": "propflow-integration-oauth",
            "iss": "propflow-api",
        },
        "attacker-key-attacker-key-attacker-key",
        algorithm="HS256",
    )
    with pytest.raises(OAuthStateError):
        decode_oauth_state(
            forged, tenant_id=tenant_a, admin_user_id=admin_a, purpose="meta_lead_ads_connect"
        )


def test_state_is_short_lived() -> None:
    import base64
    import json

    state = create_oauth_state(
        tenant_id=uuid.uuid4(),
        admin_user_id=uuid.uuid4(),
        purpose="meta_lead_ads_connect",
    )
    header, claims, _ = state.split(".")

    def part(value: str) -> dict:
        padded = value + "=" * (-len(value) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))

    payload = part(claims)
    assert payload["exp"] - payload["iat"] == 600
    assert part(header) == {"alg": "HS256", "typ": "JWT"}


# ---------------------------------------------------------------------------
# Provider configuration endpoint
# ---------------------------------------------------------------------------


def test_providers_reports_oauth_when_configured_and_manual_when_missing(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session], auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, META_FIELDS)
    from app.core.config import get_settings

    for name in (
        "google_ads_developer_token",
        "google_ads_client_id",
        "google_ads_client_secret",
    ):
        monkeypatch.setattr(get_settings(), name, None, raising=False)
    with test_session_factory() as session:
        _tenant, admin, _project = _fixture(session, label="prov")
    headers = auth_headers(admin.email, TEST_PASSWORD)
    body = client.get("/api/v1/integrations/connect/providers", headers=headers).json()
    by_provider = {row["provider"]: row for row in body}
    assert by_provider["meta_lead_ads"]["mode"] == "oauth"
    assert by_provider["meta_lead_ads"]["configured"] is True
    assert by_provider["meta_lead_ads"]["missing"] == []
    assert by_provider["google_ads"]["configured"] is False
    assert set(by_provider["google_ads"]["missing"]) == {
        "GOOGLE_ADS_DEVELOPER_TOKEN",
        "GOOGLE_ADS_CLIENT_ID",
        "GOOGLE_ADS_CLIENT_SECRET",
    }


# ---------------------------------------------------------------------------
# Meta start / callback / finalize
# ---------------------------------------------------------------------------


def test_meta_start_redirect_shape(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session], auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, META_FIELDS)
    with test_session_factory() as session:
        _tenant, admin, _project = _fixture(session, label="mstart")
    headers = auth_headers(admin.email, TEST_PASSWORD)
    response = client.get("/api/v1/integrations/connect/meta/start", headers=headers, follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    parsed = urlparse(location)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://www.facebook.com/v21.0/dialog/oauth"
    query = parse_qs(parsed.query)
    assert query["client_id"] == ["meta-app-123"]
    assert query["scope"] == ["pages_manage_leads,ads_read"]
    assert query["redirect_uri"] == ["https://app.propflow.test/api/v1/integrations/connect/meta/callback"]
    state = query["state"][0]
    claims = decode_oauth_state(state, purpose="meta_lead_ads_connect")
    assert claims.tenant_id == admin.tenant_id
    assert claims.admin_user_id == admin.id


def test_meta_start_unconfigured_returns_409_with_missing_names(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session], auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    for name in ("meta_oauth_client_id", "meta_oauth_client_secret", "oauth_redirect_base_url"):
        monkeypatch.setattr(get_settings(), name, None, raising=False)
    with test_session_factory() as session:
        _tenant, admin, _project = _fixture(session, label="mmiss")
    headers = auth_headers(admin.email, TEST_PASSWORD)
    response = client.get("/api/v1/integrations/connect/meta/start", headers=headers, follow_redirects=False)
    assert response.status_code == 409
    assert response.json()["error"] == "META_OAUTH_NOT_CONFIGURED"
    assert "META_OAUTH_CLIENT_ID" in response.json()["missing"]


def _fake_graph(*, fail_exchange: bool = False) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth/access_token") and request.method == "POST":
            if fail_exchange:
                return httpx.Response(
                    400,
                    json={"error": {"message": "Invalid OAuth access token - cannot parse the code"}},
                    request=request,
                )
            return httpx.Response(
                200, json={"access_token": "short-lived-token", "token_type": "bearer", "expires_in": 3600},
                request=request,
            )
        if request.url.path.endswith("/oauth/access_token"):
            return httpx.Response(
                200, json={"access_token": "long-lived-token", "token_type": "bearer", "expires_in": 5184000},
                request=request,
            )
        if request.url.path.endswith("/me/accounts"):
            return httpx.Response(
                200,
                json={"data": [{"id": "page-77", "name": "Keys to the Sky"}, {"id": "page-78", "name": "Marina Residency"}]},
                request=request,
            )
        if request.url.path.endswith("/page-77") or request.url.path.endswith("/page-78"):
            return httpx.Response(
                200,
                json={"id": request.url.path.rsplit("/", 1)[-1], "name": "Keys to the Sky"},
                request=request,
            )
        return httpx.Response(404, json={"error": {"message": "not found"}}, request=request)

    return httpx.MockTransport(handler)


def _patch_graph(monkeypatch: pytest.MonkeyPatch, transport: httpx.MockTransport) -> None:
    client = httpx.Client(transport=transport)
    monkeypatch.setattr(
        "app.modules.integrations.provider_clients.httpx.request", client.request
    )


def test_meta_callback_redirects_with_ticket_and_stores_encrypted_pages(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, META_FIELDS)
    _patch_graph(monkeypatch, _fake_graph())
    with test_session_factory() as session:
        _tenant, admin, _project = _fixture(session, label="mcb")
    state = create_oauth_state(
        tenant_id=admin.tenant_id,
        admin_user_id=admin.id,
        purpose="meta_lead_ads_connect",
    )
    response = client.get(
        "/api/v1/integrations/connect/meta/callback",
        params={"code": "auth-code-1", "state": state},
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers["location"]
    assert "/admin/integrations/meta/select?ticket=" in location
    assert "long-lived-token" not in location
    ticket = parse_qs(urlparse(location).query)["ticket"][0]
    from app.modules.integrations.service import get_credentials

    with test_session_factory() as session:
        connection = get_owned_connection(
            session, connection_id=uuid.UUID(ticket), tenant_id=admin.tenant_id
        )
        assert connection.connection_status == "PENDING_SELECTION"
        assert "long-lived-token" not in connection.credentials_ciphertext
        credentials = get_credentials(connection)
        assert credentials["access_token"] == "long-lived-token"
        assert [page["id"] for page in credentials["pages"]] == ["page-77", "page-78"]


def test_meta_callback_rejects_wrong_purpose_and_garbage_state(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, META_FIELDS)
    with test_session_factory() as session:
        _tenant, admin, _project = _fixture(session, label="mcbad")
    google_state = create_oauth_state(
        tenant_id=admin.tenant_id,
        admin_user_id=admin.id,
        purpose="google_ads_connect",
    )
    wrong = client.get(
        "/api/v1/integrations/connect/meta/callback",
        params={"code": "c", "state": google_state},
        follow_redirects=False,
    )
    assert wrong.status_code == 400
    forged = client.get(
        "/api/v1/integrations/connect/meta/callback",
        params={"code": "c", "state": "not-a-jwt"},
        follow_redirects=False,
    )
    assert forged.status_code == 400


def test_meta_callback_code_exchange_failure_surfaces_readable_error(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, META_FIELDS)
    _patch_graph(monkeypatch, _fake_graph(fail_exchange=True))
    with test_session_factory() as session:
        _tenant, admin, _project = _fixture(session, label="mcerr")
    state = create_oauth_state(
        tenant_id=admin.tenant_id,
        admin_user_id=admin.id,
        purpose="meta_lead_ads_connect",
    )
    response = client.get(
        "/api/v1/integrations/connect/meta/callback",
        params={"code": "expired-code", "state": state},
        follow_redirects=False,
    )
    assert response.status_code == 302
    error = parse_qs(urlparse(response.headers["location"]).query)["error"][0]
    assert "Meta could not complete the request (400)" in error
    assert "Invalid OAuth access token" in error


def test_meta_finalize_stores_encrypted_credentials_and_returns_webhook_once(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session], auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, META_FIELDS)
    _patch_graph(monkeypatch, _fake_graph())
    with test_session_factory() as session:
        tenant, admin, project = _fixture(session, label="mfin")
    state = create_oauth_state(
        tenant_id=admin.tenant_id,
        admin_user_id=admin.id,
        purpose="meta_lead_ads_connect",
    )
    callback = client.get(
        "/api/v1/integrations/connect/meta/callback",
        params={"code": "auth-code-1", "state": state},
        follow_redirects=False,
    )
    ticket = parse_qs(urlparse(callback.headers["location"]).query)["ticket"][0]
    headers = auth_headers(admin.email, TEST_PASSWORD)
    pages = client.get(
        "/api/v1/integrations/connect/meta/pages", params={"connection_id": ticket}, headers=headers
    )
    assert [page["id"] for page in pages.json()["pages"]] == ["page-77", "page-78"]
    finalized = client.post(
        "/api/v1/integrations/connect/meta/finalize",
        json={"connection_id": ticket, "page_id": "page-77", "project_id": str(project.id)},
        headers=headers,
    )
    assert finalized.status_code == 200, finalized.text
    body = finalized.json()
    assert body["webhook_url"] == "https://app.propflow.test/api/v1/webhooks/meta"
    assert len(body["webhook_verify_token"]) >= 32
    assert body["connection"]["external_account_id"] == "page-77"
    assert body["connection"]["is_active"] is True
    assert body["connection"]["project_id"] == str(project.id)
    assert body["subscription_checklist"]
    from app.modules.integrations.service import get_credentials

    with test_session_factory() as session:
        connection = session.get(IntegrationConnection, uuid.UUID(ticket))
        assert connection is not None
        assert connection.connection_status == "ACTIVE"
        assert "long-lived-token" not in connection.credentials_ciphertext
        assert get_credentials(connection)["access_token"] == "long-lived-token"
        assert connection.webhook_verify_token_hash is not None
        assert body["webhook_verify_token"] not in str(
            [row.webhook_verify_token_hash for row in session.query(IntegrationConnection).all()]
        )
        # The pending ticket row was reused; no stale pending rows remain.
        pending = [
            row
            for row in session.query(IntegrationConnection).all()
            if row.connection_status == "PENDING_SELECTION"
        ]
        assert pending == []
    listed = client.get("/api/v1/integrations/connections", headers=headers)
    assert "long-lived-token" not in listed.text
    status_response = client.get(
        f"/api/v1/integrations/connect/meta/status/{ticket}", headers=headers
    )
    assert status_response.status_code == 200
    assert status_response.json()["health"] == "unverified"
    assert status_response.json()["configured"] is True


def test_meta_finalize_rejects_other_tenants_ticket(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session], auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, META_FIELDS)
    _patch_graph(monkeypatch, _fake_graph())
    with test_session_factory() as session:
        _tenant, admin, _project = _fixture(session, label="mfin2")
        _other, other_admin, other_project = _fixture(session, label="mfin3")
    state = create_oauth_state(
        tenant_id=admin.tenant_id, admin_user_id=admin.id, purpose="meta_lead_ads_connect"
    )
    callback = client.get(
        "/api/v1/integrations/connect/meta/callback",
        params={"code": "x", "state": state},
        follow_redirects=False,
    )
    ticket = parse_qs(urlparse(callback.headers["location"]).query)["ticket"][0]
    headers = auth_headers(other_admin.email, TEST_PASSWORD)
    refused = client.post(
        "/api/v1/integrations/connect/meta/finalize",
        json={"connection_id": ticket, "page_id": "page-77", "project_id": str(other_project.id)},
        headers=headers,
    )
    assert refused.status_code == 404


# ---------------------------------------------------------------------------
# Test-connection endpoints (real HTTP only when clicked; mocked here)
# ---------------------------------------------------------------------------


def _connected_meta(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
    auth_headers,
    monkeypatch: pytest.MonkeyPatch,
):
    _configure(monkeypatch, META_FIELDS)
    _patch_graph(monkeypatch, _fake_graph())
    with test_session_factory() as session:
        _tenant, admin, project = _fixture(session, label="mtest")
    state = create_oauth_state(
        tenant_id=admin.tenant_id, admin_user_id=admin.id, purpose="meta_lead_ads_connect"
    )
    callback = client.get(
        "/api/v1/integrations/connect/meta/callback",
        params={"code": "x", "state": state},
        follow_redirects=False,
    )
    ticket = parse_qs(urlparse(callback.headers["location"]).query)["ticket"][0]
    headers = auth_headers(admin.email, TEST_PASSWORD)
    client.post(
        "/api/v1/integrations/connect/meta/finalize",
        json={"connection_id": ticket, "page_id": "page-77", "project_id": str(project.id)},
        headers=headers,
    )
    return headers, ticket


def test_meta_test_success_and_failure_record_health(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session], auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers, ticket = _connected_meta(client, test_session_factory, auth_headers, monkeypatch)
    ok = client.post(
        "/api/v1/integrations/connect/meta/test", params={"connection_id": ticket}, headers=headers
    )
    assert ok.status_code == 200
    assert ok.json()["ok"] is True

    def failing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"error": {"message": "Error validating access token: session has expired"}},
            request=request,
        )

    _patch_graph(monkeypatch, httpx.MockTransport(failing))
    bad = client.post(
        "/api/v1/integrations/connect/meta/test", params={"connection_id": ticket}, headers=headers
    )
    assert bad.status_code == 502
    with test_session_factory() as session:
        connection = session.get(IntegrationConnection, uuid.UUID(ticket))
        assert connection.last_success_at is not None
        assert "session has expired" in connection.last_error

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    _patch_graph(monkeypatch, httpx.MockTransport(unreachable))
    gone = client.post(
        "/api/v1/integrations/connect/meta/test", params={"connection_id": ticket}, headers=headers
    )
    assert gone.status_code == 502
    assert "could not be reached" in gone.json()["error"]["message"]


# ---------------------------------------------------------------------------
# Google flows
# ---------------------------------------------------------------------------


def _fake_google(*, refresh: bool = True) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.googleapis.com" and request.url.path == "/token":
            form = parse_qs(request.content.decode())
            if form.get("grant_type") == ["authorization_code"]:
                if not refresh:
                    return httpx.Response(
                        200, json={"access_token": "ya29.m", "expires_in": 3600}, request=request
                    )
                return httpx.Response(
                    200,
                    json={"access_token": "ya29.m", "refresh_token": "1//refresh.m", "expires_in": 3600},
                    request=request,
                )
            return httpx.Response(200, json={"access_token": "ya29.refreshed", "expires_in": 3600}, request=request)
        if request.url.path.endswith("customers:listAccessibleCustomers"):
            return httpx.Response(
                200, json={"resourceNames": ["customers/1234567890"]}, request=request
            )
        return httpx.Response(404, json={"error": {"message": "nope"}}, request=request)

    return httpx.MockTransport(handler)


def _patch_google(monkeypatch: pytest.MonkeyPatch, transport: httpx.MockTransport) -> None:
    client = httpx.Client(transport=transport)
    monkeypatch.setattr(
        "app.modules.integrations.provider_clients.httpx.request", client.request
    )


def test_google_start_includes_offline_scope_and_state(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session], auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, GOOGLE_FIELDS)
    with test_session_factory() as session:
        _tenant, admin, _project = _fixture(session, label="gstart")
    headers = auth_headers(admin.email, TEST_PASSWORD)
    response = client.get("/api/v1/integrations/connect/google/start", headers=headers, follow_redirects=False)
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["scope"] == ["https://www.googleapis.com/auth/adwords"]
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]
    decode_oauth_state(query["state"][0], purpose="google_ads_connect")


def test_google_callback_finalize_and_test_roundtrip(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session], auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, GOOGLE_FIELDS)
    _patch_google(monkeypatch, _fake_google())
    with test_session_factory() as session:
        _tenant, admin, project = _fixture(session, label="gfull")
    state = create_oauth_state(
        tenant_id=admin.tenant_id, admin_user_id=admin.id, purpose="google_ads_connect"
    )
    callback = client.get(
        "/api/v1/integrations/connect/google/callback",
        params={"code": "g-code", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code == 302
    assert "/admin/integrations/google/select?ticket=" in callback.headers["location"]
    assert "1//refresh.m" not in callback.headers["location"]
    ticket = parse_qs(urlparse(callback.headers["location"]).query)["ticket"][0]
    headers = auth_headers(admin.email, TEST_PASSWORD)
    finalized = client.post(
        "/api/v1/integrations/connect/google/finalize",
        json={"connection_id": ticket, "customer_id": "1234567890", "project_id": str(project.id)},
        headers=headers,
    )
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["external_account_id"] == "1234567890"
    tested = client.post(
        "/api/v1/integrations/connect/google/test", params={"connection_id": ticket}, headers=headers
    )
    assert tested.status_code == 200
    assert tested.json()["ok"] is True
    from app.modules.integrations.service import get_credentials

    with test_session_factory() as session:
        connection = get_owned_connection(
            session, connection_id=uuid.UUID(ticket), tenant_id=admin.tenant_id
        )
        assert "1//refresh.m" not in connection.credentials_ciphertext
        credentials = get_credentials(connection)
        assert credentials["refresh_token"] == "1//refresh.m"
        assert credentials["developer_token"] == "dev-token"


def test_google_callback_without_refresh_token_is_not_faked_connected(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, GOOGLE_FIELDS)
    _patch_google(monkeypatch, _fake_google(refresh=False))
    with test_session_factory() as session:
        _tenant, admin, _project = _fixture(session, label="gnoref")
    state = create_oauth_state(
        tenant_id=admin.tenant_id, admin_user_id=admin.id, purpose="google_ads_connect"
    )
    response = client.get(
        "/api/v1/integrations/connect/google/callback",
        params={"code": "g-code", "state": state},
        follow_redirects=False,
    )
    assert response.status_code == 302
    error = parse_qs(urlparse(response.headers["location"]).query).get("error")
    assert error and "refresh token" in error[0].lower()


def test_google_manual_requires_every_field_and_encrypts(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session], auth_headers,
) -> None:
    with test_session_factory() as session:
        _tenant, admin, project = _fixture(session, label="gman")
    headers = auth_headers(admin.email, TEST_PASSWORD)
    complete = {
        "developer_token": "devtok",
        "refresh_token": "1//refresh.t",
        "client_id": "cid.apps.googleusercontent.com",
        "client_secret": "csecret",
        "customer_id": "9876543210",
        "project_id": str(project.id),
    }
    for missing in sorted(complete):
        payload = {key: value for key, value in complete.items() if key != missing}
        rejected = client.post("/api/v1/integrations/connect/google/manual", json=payload, headers=headers)
        assert rejected.status_code == 422, missing
    malformed = client.post(
        "/api/v1/integrations/connect/google/manual",
        json={**complete, "customer_id": "not-a-number"},
        headers=headers,
    )
    assert malformed.status_code == 422
    created = client.post(
        "/api/v1/integrations/connect/google/manual", json=complete, headers=headers
    )
    assert created.status_code == 200, created.text
    for secret in ("devtok", "1//refresh.t", "csecret"):
        assert secret not in created.text
    from app.modules.integrations.service import get_credentials

    with test_session_factory() as session:
        connection = get_owned_connection(
            session,
            connection_id=uuid.UUID(created.json()["id"]),
            tenant_id=admin.tenant_id,
        )
        assert connection.provider == "google_ads"
        assert connection.connection_status == "ACTIVE"
        assert "1//refresh.t" not in connection.credentials_ciphertext
        assert get_credentials(connection)["refresh_token"] == "1//refresh.t"
    listed = client.get("/api/v1/integrations/connections", headers=headers)
    assert "1//refresh.t" not in listed.text


def test_connection_revoke_deletes_pending_ticket(
    client: TestClient, override_db: None, seeded_roles: None,
    test_session_factory: sessionmaker[Session], auth_headers,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, META_FIELDS)
    _patch_graph(monkeypatch, _fake_graph())
    with test_session_factory() as session:
        _tenant, admin, _project = _fixture(session, label="mrev")
    headers = auth_headers(admin.email, TEST_PASSWORD)
    state = create_oauth_state(
        tenant_id=admin.tenant_id, admin_user_id=admin.id, purpose="meta_lead_ads_connect"
    )
    callback = client.get(
        "/api/v1/integrations/connect/meta/callback",
        params={"code": "x", "state": state},
        follow_redirects=False,
    )
    ticket = parse_qs(urlparse(callback.headers["location"]).query)["ticket"][0]
    assert (
        client.delete(f"/api/v1/integrations/connect/connections/{ticket}", headers=headers).status_code
        == 204
    )
    with test_session_factory() as session:
        assert session.get(IntegrationConnection, uuid.UUID(ticket)) is None
    assert client.get(f"/api/v1/integrations/connect/meta/status/{ticket}", headers=headers).status_code == 404
