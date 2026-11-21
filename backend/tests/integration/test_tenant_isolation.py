"""Two-tenant isolation acceptance tests."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from tests.project_support import create_project
from tests.support import TEST_PASSWORD


def test_admin_cannot_read_another_tenants_project(
    client: TestClient,
    override_db: None,
    default_tenant: Tenant,
    user_factory: Callable[..., User],
    test_session_factory: sessionmaker[Session],
) -> None:
    other = Tenant(slug="other", name="Other Realty")
    with test_session_factory() as session:
        session.add(other)
        session.commit()

    admin_a = user_factory(role=RoleName.ADMIN, tenant=default_tenant)
    admin_b = user_factory(role=RoleName.ADMIN, tenant=other)
    token_a = client.post("/api/v1/auth/login", json={"email": admin_a.email, "password": TEST_PASSWORD}).json()["access_token"]
    token_b = client.post("/api/v1/auth/login", json={"email": admin_b.email, "password": TEST_PASSWORD}).json()["access_token"]
    project = create_project(client, {"Authorization": f"Bearer {token_b}"})

    response = client.get(f"/api/v1/projects/{project['id']}", headers={"Authorization": f"Bearer {token_a}"})
    assert response.status_code == 404


def test_admin_listings_only_include_own_tenant(
    client: TestClient,
    override_db: None,
    default_tenant: Tenant,
    user_factory: Callable[..., User],
    test_session_factory: sessionmaker[Session],
) -> None:
    other = Tenant(slug="other", name="Other Realty")
    with test_session_factory() as session:
        session.add(other)
        session.commit()
    admin_a = user_factory(role=RoleName.ADMIN, tenant=default_tenant)
    admin_b = user_factory(role=RoleName.ADMIN, tenant=other)
    token_a = client.post("/api/v1/auth/login", json={"email": admin_a.email, "password": TEST_PASSWORD}).json()["access_token"]
    token_b = client.post("/api/v1/auth/login", json={"email": admin_b.email, "password": TEST_PASSWORD}).json()["access_token"]
    own = create_project(client, {"Authorization": f"Bearer {token_a}"})
    other_project = create_project(client, {"Authorization": f"Bearer {token_b}"})

    response = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token_a}"})
    ids = {item["id"] for item in response.json()["items"]}
    assert own["id"] in ids
    assert other_project["id"] not in ids


def test_tenant_settings_are_isolated_and_admin_only(
    client: TestClient,
    override_db: None,
    default_tenant: Tenant,
    user_factory: Callable[..., User],
    test_session_factory: sessionmaker[Session],
) -> None:
    other = Tenant(slug="other", name="Other Realty", brand_name="Other Realty")
    with test_session_factory() as session:
        session.add(other)
        session.commit()
    admin_a = user_factory(role=RoleName.ADMIN, tenant=default_tenant)
    buyer_a = user_factory(tenant=default_tenant)
    token_admin = client.post("/api/v1/auth/login", json={"email": admin_a.email, "password": TEST_PASSWORD}).json()["access_token"]
    token_buyer = client.post("/api/v1/auth/login", json={"email": buyer_a.email, "password": TEST_PASSWORD}).json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {token_admin}"}
    buyer_headers = {"Authorization": f"Bearer {token_buyer}"}

    assert client.put("/api/v1/tenancy/settings", json={"brand_name": "Nope"}, headers=buyer_headers).status_code == 403
    updated = client.put("/api/v1/tenancy/settings", json={"brand_name": "Acme Homes"}, headers=admin_headers)
    assert updated.status_code == 200
    assert updated.json()["brand_name"] == "Acme Homes"
    assert client.get("/api/v1/tenancy/settings", headers=admin_headers).json()["brand_name"] == "Acme Homes"
    public = client.get("/api/v1/tenancy/public/other")
    assert public.status_code == 200
    assert public.json()["brand_name"] == "Other Realty"


def test_tenant_signup_creates_admin_and_returns_tokens(
    client: TestClient,
    override_db: None,
    test_session_factory: sessionmaker[Session],
) -> None:
    response = client.post("/api/v1/tenancy/signup", json={
        "name": "New Realty",
        "slug": "new-realty",
        "full_name": "Organization Admin",
        "email": "admin@new-realty.example",
        "password": TEST_PASSWORD,
    })
    assert response.status_code == 201
    assert response.json()["access_token"]
    profile = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"})
    assert profile.json()["role"]["name"] == "ADMIN"
    assert profile.json()["tenant_id"]
