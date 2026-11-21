"""Cross-tenant isolation across users, leads, bookings, settings, analytics."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from tests.lead_support import create_lead
from tests.project_support import create_project
from tests.booking_support import create_booking, create_slot
from tests.support import TEST_PASSWORD


@pytest.fixture()
def other_tenant(test_session_factory: sessionmaker[Session]) -> Tenant:
    with test_session_factory() as session:
        tenant = Tenant(slug="other-co", name="Other Co")
        session.add(tenant)
        session.commit()
        session.refresh(tenant)
        return tenant


def _login(client: TestClient, user: User) -> dict[str, str]:
    token = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": TEST_PASSWORD},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_users_list_is_tenant_scoped(
    client: TestClient,
    override_db: None,
    default_tenant: Tenant,
    other_tenant: Tenant,
    user_factory: Callable[..., User],
) -> None:
    admin = user_factory(role=RoleName.ADMIN, tenant=default_tenant)
    user_factory(tenant=other_tenant, email="stranger@other.example")
    headers = _login(client, admin)

    body = client.get("/api/v1/users", headers=headers).json()
    emails = {item["email"] for item in body["items"]}
    assert admin.email in emails
    assert "stranger@other.example" not in emails
    assert client.get("/api/v1/users/metrics", headers=headers).json()["total"] == 1


def test_lead_duplicate_check_does_not_leak_other_tenant(
    client: TestClient,
    override_db: None,
    default_tenant: Tenant,
    other_tenant: Tenant,
    user_factory: Callable[..., User],
) -> None:
    admin_a = user_factory(role=RoleName.ADMIN, tenant=default_tenant)
    admin_b = user_factory(role=RoleName.ADMIN, tenant=other_tenant)
    project_b = create_project(client, _login(client, admin_b), status="ACTIVE")
    create_lead(
        client,
        project_id=project_b["id"],
        email="shared@example.com",
        phone="+919999999999",
    )

    headers_a = _login(client, admin_a)
    dup = client.get(
        "/api/v1/leads/duplicates/check",
        params={"email": "shared@example.com"},
        headers=headers_a,
    ).json()
    assert dup["duplicate"] is False
    assert dup["matching_lead_ids"] == []


def test_public_lead_intake_uses_project_tenant(
    client: TestClient,
    override_db: None,
    default_tenant: Tenant,
    other_tenant: Tenant,
    user_factory: Callable[..., User],
) -> None:
    admin_b = user_factory(role=RoleName.ADMIN, tenant=other_tenant)
    project_b = create_project(client, _login(client, admin_b), status="ACTIVE")
    lead = create_lead(client, project_id=project_b["id"])

    # Lead created publicly inherits the project's tenant (other_tenant), not default
    assert lead["project_id"] == project_b["id"]
    admin_a = user_factory(role=RoleName.ADMIN, tenant=default_tenant)
    resp = client.get(
        "/api/v1/leads",
        params={"search": lead["email"]},
        headers=_login(client, admin_a),
    )
    assert resp.json()["total"] == 0


def test_booking_isolation_between_tenants(
    client: TestClient,
    override_db: None,
    default_tenant: Tenant,
    other_tenant: Tenant,
    user_factory: Callable[..., User],
) -> None:
    admin_b = user_factory(role=RoleName.ADMIN, tenant=other_tenant)
    buyer_b = user_factory(tenant=other_tenant)
    headers_b = _login(client, admin_b)
    project_b = create_project(client, headers_b, status="ACTIVE")
    lead_b = create_lead(client, project_id=project_b["id"], email=buyer_b.email)
    from datetime import UTC, datetime, timedelta
    start = datetime.now(UTC) + timedelta(days=2)
    slot_b = create_slot(
        client,
        headers_b,
        project_id=project_b["id"],
        start_time=start,
        end_time=start + timedelta(hours=1),
    )
    booking_b = create_booking(
        client, _login(client, buyer_b), slot_id=slot_b["id"], lead_id=lead_b["id"]
    )

    admin_a = user_factory(role=RoleName.ADMIN, tenant=default_tenant)
    resp = client.get(
        f"/api/v1/bookings/{booking_b['id']}",
        headers=_login(client, admin_a),
    )
    assert resp.status_code == 404


def test_settings_and_audit_are_tenant_scoped(
    client: TestClient,
    override_db: None,
    default_tenant: Tenant,
    other_tenant: Tenant,
    user_factory: Callable[..., User],
) -> None:
    admin_a = user_factory(role=RoleName.ADMIN, tenant=default_tenant)
    admin_b = user_factory(role=RoleName.ADMIN, tenant=other_tenant)
    headers_a = _login(client, admin_a)
    headers_b = _login(client, admin_b)

    client.patch(
        "/api/v1/settings/reminders",
        json={"enabled_24h": False},
        headers=headers_a,
    )
    body_b = client.get("/api/v1/settings", headers=headers_b).json()
    assert body_b["reminders"]["enabled_24h"] is True  # B unaffected by A's change

    logs_a = client.get("/api/v1/settings/audit-logs", headers=headers_a).json()
    logs_b = client.get("/api/v1/settings/audit-logs", headers=headers_b).json()
    ids_a = {log["actor_id"] for log in logs_a["items"]}
    assert logs_b["total"] == 0 or str(admin_b.id) not in ids_a


def test_admin_cannot_assign_another_tenants_executive_to_handoff(
    client: TestClient,
    override_db: None,
    default_tenant: Tenant,
    other_tenant: Tenant,
    user_factory: Callable[..., User],
) -> None:
    admin_a = user_factory(role=RoleName.ADMIN, tenant=default_tenant)
    buyer_a = user_factory(tenant=default_tenant)
    foreign_exec = user_factory(role=RoleName.SALES_EXECUTIVE, tenant=other_tenant)

    headers_a = _login(client, admin_a)
    project = create_project(client, headers_a, status="ACTIVE")
    lead = create_lead(client, project_id=project["id"], email=buyer_a.email)
    conversation = client.post(
        "/api/v1/conversations",
        json={"lead_id": lead["id"], "project_id": project["id"]},
        headers=_login(client, buyer_a),
    ).json()
    handoff = client.post(
        "/api/v1/handoffs",
        json={"conversation_id": conversation["id"]},
        headers=_login(client, buyer_a),
    ).json()

    response = client.post(
        f"/api/v1/handoffs/{handoff['id']}/assign",
        json={"executive_id": str(foreign_exec.id)},
        headers=headers_a,
    )
    assert response.status_code in (400, 404)


def test_suspended_tenant_cannot_log_in_or_refresh(
    client: TestClient,
    override_db: None,
    default_tenant: Tenant,
    user_factory: Callable[..., User],
    test_session_factory: sessionmaker[Session],
) -> None:
    user = user_factory(tenant=default_tenant)
    login = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
    ).json()

    with test_session_factory() as session:
        tenant = session.get(Tenant, default_tenant.id)
        tenant.status = "suspended"
        session.commit()

    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": TEST_PASSWORD},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": login["refresh_token"]},
        ).status_code
        == 401
    )


def test_admin_cannot_access_cross_tenant_settings_templates(
    client: TestClient,
    override_db: None,
    default_tenant: Tenant,
    other_tenant: Tenant,
    user_factory: Callable[..., User],
) -> None:
    admin_a = user_factory(role=RoleName.ADMIN, tenant=default_tenant)
    admin_b = user_factory(role=RoleName.ADMIN, tenant=other_tenant)
    headers_b = _login(client, admin_b)
    template_b = client.get("/api/v1/settings/templates", headers=headers_b).json()["items"][0]

    response = client.get(
        f"/api/v1/settings/templates/{template_b['id']}",
        headers=_login(client, admin_a),
    )
    assert response.status_code == 404


def test_dashboard_metrics_are_tenant_scoped(
    client: TestClient,
    override_db: None,
    default_tenant: Tenant,
    other_tenant: Tenant,
    user_factory: Callable[..., User],
) -> None:
    admin_b = user_factory(role=RoleName.ADMIN, tenant=other_tenant)
    project_b = create_project(client, _login(client, admin_b), status="ACTIVE")
    create_lead(client, project_id=project_b["id"], full_name="Only Tenant B Lead")

    admin_a = user_factory(role=RoleName.ADMIN, tenant=default_tenant)
    summary = client.get(
        "/api/v1/dashboard/summary",
        headers=_login(client, admin_a),
    ).json()
    assert summary["total_leads"] == 0
