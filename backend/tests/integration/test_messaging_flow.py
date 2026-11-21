"""End-to-end messaging flow and operator control-plane integration tests."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.security import hash_password
from app.modules.messaging.models import MessageDelivery, MessageTemplate, TriggerRule
from app.modules.operator.models import OperatorUser
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from tests.lead_support import create_lead
from tests.project_support import create_project
from tests.support import TEST_PASSWORD


def _login(client: TestClient, user: User) -> dict[str, str]:
    token = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _operator(session: Session, *, role: str = "OWNER") -> OperatorUser:
    operator = OperatorUser(
        email=f"operator-{uuid4().hex[:8]}@example.com",
        full_name="Test Operator",
        password_hash=hash_password(TEST_PASSWORD),
        role=role,
        permissions=[],
        is_active=True,
    )
    session.add(operator)
    session.commit()
    session.refresh(operator)
    return operator


def _operator_headers(client: TestClient, operator: OperatorUser) -> dict[str, str]:
    token = client.post(
        "/api/v1/operator/auth/login",
        json={"email": operator.email, "password": TEST_PASSWORD},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_lead_create_emits_messaging_delivery_and_admin_can_configure_rules(
    client: TestClient,
    override_db: None,
    default_tenant: Tenant,
    user_factory: Callable[..., User],
    test_session_factory: sessionmaker[Session],
) -> None:
    admin = user_factory(role=RoleName.ADMIN, tenant=default_tenant)
    headers = _login(client, admin)
    project = create_project(client, headers, status="ACTIVE")

    # Admin creates a Hindi WhatsApp template + lead.created rule.
    template = client.post(
        "/api/v1/messaging/templates",
        json={
            "name": "Hindi Lead Welcome",
            "channel": "WHATSAPP",
            "language": "hi",
            "body": "नमस्ते {first_name}, {project_name} में आपका स्वागत है।",
        },
        headers=headers,
    ).json()
    rule = client.post(
        "/api/v1/messaging/rules",
        json={
            "event": "lead.created",
            "channel": "WHATSAPP",
            "template_id": template["id"],
            "enabled": True,
            "delay_minutes": 0,
        },
        headers=headers,
    ).json()
    assert rule["enabled"] is True

    lead = create_lead(client, project_id=project["id"], full_name="Asha Patel")

    with test_session_factory() as session:
        deliveries = session.query(MessageDelivery).filter(
            MessageDelivery.tenant_id == default_tenant.id
        ).all()
        assert len(deliveries) == 1
        delivery = deliveries[0]
        assert delivery.channel == "WHATSAPP"
        assert delivery.event == "lead.created"
        assert delivery.entity_id == lead["id"] or str(delivery.entity_id) == str(lead["id"])
        assert "Asha" in delivery.body
        assert delivery.status == "QUEUED"

    # Delivery log endpoint returns the row.
    log = client.get("/api/v1/messaging/deliveries", headers=headers).json()
    assert log["total"] == 1
    assert log["items"][0]["event"] == "lead.created"


def test_send_test_endpoint_creates_immediate_delivery(
    client: TestClient,
    override_db: None,
    default_tenant: Tenant,
    user_factory: Callable[..., User],
) -> None:
    admin = user_factory(role=RoleName.ADMIN, tenant=default_tenant)
    headers = _login(client, admin)
    response = client.post(
        "/api/v1/messaging/send-test",
        json={"channel": "WHATSAPP", "to_address": "+919800000000", "body": "Test message"},
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["status"] == "QUEUED"
    assert response.json()["event"] == "message.test"


def test_operator_can_provision_tenant_and_suspend_it(
    client: TestClient,
    override_db: None,
    default_tenant: Tenant,
    user_factory: Callable[..., User],
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        operator = _operator(session)
    op_headers = _operator_headers(client, operator)

    # Operator provisions a new tenant with an admin.
    provisioned = client.post(
        "/api/v1/operator/tenants",
        json={
            "slug": "new-co",
            "name": "New Co",
            "admin_email": "admin@new-co.example",
            "admin_full_name": "New Admin",
            "admin_password": TEST_PASSWORD,
        },
        headers=op_headers,
    )
    assert provisioned.status_code == 201, provisioned.text
    tenant_id = provisioned.json()["id"]
    assert provisioned.json()["slug"] == "new-co"

    # New admin can log in and access tenant-scoped data.
    admin_token = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@new-co.example", "password": TEST_PASSWORD},
    ).json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert me.status_code == 200
    assert me.json()["tenant_id"] == tenant_id
    assert me.json()["role"]["name"] == "ADMIN"

    # Operator suspends the tenant; tenant requests are rejected.
    suspended = client.patch(
        f"/api/v1/operator/tenants/{tenant_id}/status",
        json={"status": "suspended"},
        headers=op_headers,
    )
    assert suspended.status_code == 200
    blocked = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert blocked.status_code == 403


def test_tenant_token_is_rejected_on_operator_endpoints(
    client: TestClient,
    override_db: None,
    default_tenant: Tenant,
    user_factory: Callable[..., User],
    test_session_factory: sessionmaker[Session],
) -> None:
    admin = user_factory(role=RoleName.ADMIN, tenant=default_tenant)
    tenant_headers = _login(client, admin)
    response = client.get("/api/v1/operator/tenants", headers=tenant_headers)
    assert response.status_code == 401

    with test_session_factory() as session:
        operator = _operator(session)
    op_headers = _operator_headers(client, operator)
    response = client.get("/api/v1/users", headers=op_headers)
    assert response.status_code == 401


def test_operator_plan_management_and_audit_log(
    client: TestClient,
    override_db: None,
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        operator = _operator(session)
    op_headers = _operator_headers(client, operator)

    plan = client.post(
        "/api/v1/operator/plans",
        json={
            "code": "pro",
            "name": "Professional",
            "price_paise": 99900,
            "max_users": 25,
            "leads_per_month": 5000,
            "whatsapp_msgs_per_month": 10000,
        },
        headers=op_headers,
    )
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["id"]
    assert plan.json()["price_paise"] == 99900

    updated = client.patch(
        f"/api/v1/operator/plans/{plan_id}",
        json={"price_paise": 149900, "max_users": 50},
        headers=op_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["price_paise"] == 149900
    assert updated.json()["max_users"] == 50

    # Audit log records both actions.
    logs = client.get("/api/v1/operator/audit-logs", headers=op_headers).json()
    actions = {log["action"] for log in logs}
    assert "PLAN_CREATED" in actions
    assert "PLAN_UPDATED" in actions
