"""Integration tests for the broker/channel-partner registry and performance."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.brokers.models import Broker, BrokerStatus
from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.postsales import service as postsales_service
from app.modules.postsales.schemas import (
    BrokerCommissionCreateRequest,
    SaleBookingCreateRequest,
)
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User


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
        "headers": headers,
    }


def _register(client: TestClient, env: dict, **overrides) -> dict:
    payload = {
        "agency_name": "Realty Partners",
        "contact_name": "Ravi Shah",
        "email": "ravi@realtypartners.example",
        "phone": "+919811111111",
        "rera_id": "RERA-123",
        "notes": "Primary channel partner.",
    }
    payload.update(overrides)
    response = client.post("/api/v1/brokers", json=payload, headers=env["headers"])
    assert response.status_code == 201, response.text
    return response.json()


def _create_commission(
    env: dict, *, broker_name: str, amount_paise: int
) -> None:
    """Mirror the post-sales commission fixture: converted lead -> sale booking."""

    with env["factory"]() as session:
        admin = session.get(User, env["admin_id"])
        project = Project(
            tenant_id=env["tenant_id"],
            name="Tower",
            slug=f"tower-{uuid4().hex[:8]}",
            location="Pune",
            status=ProjectStatus.ACTIVE.value,
            created_by=admin.id,
        )
        session.add(project)
        session.flush()
        lead = Lead(
            tenant_id=env["tenant_id"],
            full_name="Buyer One",
            email=f"buyer-{uuid4().hex[:8]}@sales.example",
            phone="+919800000001",
            project_id=project.id,
            source=LeadSource.WEBSITE.value,
            status=LeadStatus.CONVERTED.value,
            consent_to_contact=True,
        )
        session.add(lead)
        session.commit()

        booking = postsales_service.create_booking(
            session,
            actor=admin,
            payload=SaleBookingCreateRequest(
                lead_id=lead.id, unit_number="A-101", consideration_paise=10_00_00_00
            ),
        )
        postsales_service.create_commission(
            session,
            actor=admin,
            booking_id=booking.id,
            payload=BrokerCommissionCreateRequest(
                broker_name=broker_name,
                broker_phone="+919811111111",
                amount_paise=amount_paise,
                basis={"percent": 2},
            ),
        )


def test_register_broker_and_idempotent_duplicate(client: TestClient, env: dict) -> None:
    body = _register(client, env)
    assert body["agency_name"] == "Realty Partners"
    assert body["contact_name"] == "Ravi Shah"
    assert body["status"] == BrokerStatus.ACTIVE.value
    assert body["created_by"] == str(env["admin_id"])

    repeat = client.post(
        "/api/v1/brokers",
        json={"agency_name": "Realty Partners", "contact_name": "Ravi Shah"},
        headers=env["headers"],
    )
    assert repeat.status_code == 201, repeat.text
    assert repeat.json()["id"] == body["id"]
    with env["factory"]() as session:
        total = session.query(Broker).count()
    assert total == 1


def test_update_fields_and_status_transition(client: TestClient, env: dict) -> None:
    broker_id = _register(client, env)["id"]
    response = client.patch(
        f"/api/v1/brokers/{broker_id}",
        json={
            "contact_name": "Ravi S. Shah",
            "phone": "+919822222222",
            "status": "INACTIVE",
            "notes": "Dormant this quarter.",
        },
        headers=env["headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["contact_name"] == "Ravi S. Shah"
    assert body["phone"] == "+919822222222"
    assert body["status"] == BrokerStatus.INACTIVE.value
    assert body["notes"] == "Dormant this quarter."
    assert body["agency_name"] == "Realty Partners"

    for status_value in ("SUSPENDED", "ACTIVE"):
        response = client.patch(
            f"/api/v1/brokers/{broker_id}",
            json={"status": status_value},
            headers=env["headers"],
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == status_value


def test_update_rejects_agency_identity_changes(client: TestClient, env: dict) -> None:
    broker_id = _register(client, env)["id"]
    response = client.patch(
        f"/api/v1/brokers/{broker_id}",
        json={"agency_name": "Renamed Realty"},
        headers=env["headers"],
    )
    assert response.status_code == 422


def test_list_filter_and_search(client: TestClient, env: dict) -> None:
    _register(client, env)
    other = client.post(
        "/api/v1/brokers",
        json={"agency_name": "City Homes", "contact_name": "Anita Rao"},
        headers=env["headers"],
    )
    assert other.status_code == 201, other.text
    other_id = other.json()["id"]
    response = client.patch(
        f"/api/v1/brokers/{other_id}", json={"status": "SUSPENDED"}, headers=env["headers"]
    )
    assert response.status_code == 200

    listed = client.get("/api/v1/brokers", headers=env["headers"])
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 2

    filtered = client.get("/api/v1/brokers?status=SUSPENDED", headers=env["headers"])
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["agency_name"] == "City Homes"

    agency_search = client.get("/api/v1/brokers?search=realty", headers=env["headers"])
    assert [item["contact_name"] for item in agency_search.json()["items"]] == ["Ravi Shah"]
    contact_search = client.get("/api/v1/brokers?search=ANITA", headers=env["headers"])
    assert [item["agency_name"] for item in contact_search.json()["items"]] == ["City Homes"]


def test_cross_tenant_read_and_update_return_404(
    client: TestClient, env: dict, user_factory, auth_headers
) -> None:
    other_tenant = Tenant(slug=f"o-{uuid4().hex[:8]}", name="Other")
    with env["factory"]() as session:
        session.add(other_tenant)
        session.flush()
        other = Broker(
            tenant_id=other_tenant.id,
            agency_name="Other Realty",
            contact_name="Other Contact",
        )
        session.add(other)
        session.commit()
        other_id = str(other.id)

    response = client.get(f"/api/v1/brokers/{other_id}", headers=env["headers"])
    assert response.status_code == 404
    response = client.patch(
        f"/api/v1/brokers/{other_id}", json={"notes": "stolen"}, headers=env["headers"]
    )
    assert response.status_code == 404
    response = client.get(f"/api/v1/brokers/{other_id}/performance", headers=env["headers"])
    assert response.status_code == 404
    listed = client.get("/api/v1/brokers", headers=env["headers"])
    assert listed.json()["total"] == 0


def test_performance_aggregates_commissions_by_contact_name(
    client: TestClient, env: dict
) -> None:
    broker_id = _register(client, env)["id"]
    _create_commission(env, broker_name="Ravi Shah", amount_paise=30_00_00)
    _create_commission(env, broker_name="Ravi Shah", amount_paise=20_00_00)
    # Agency-only matches are intentionally excluded by the deterministic rule.
    _create_commission(env, broker_name="Realty Partners", amount_paise=99_00_00)

    response = client.get(f"/api/v1/brokers/{broker_id}/performance", headers=env["headers"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["broker_id"] == broker_id
    assert body["total_commission_paise"] == 50_00_00
    assert body["deal_count"] == 2
    assert body["by_status"] == {
        "PENDING": 50_00_00,
        "PAYABLE": 0,
        "PAID": 0,
        "REVERSED": 0,
    }


def test_role_permissions(client: TestClient, env: dict, user_factory, auth_headers) -> None:
    broker_id = _register(client, env)["id"]
    sales = user_factory(role=RoleName.SALES_EXECUTIVE)
    sales_headers = auth_headers(sales.email)
    response = client.get("/api/v1/brokers", headers=sales_headers)
    assert response.status_code == 200
    response = client.get(f"/api/v1/brokers/{broker_id}", headers=sales_headers)
    assert response.status_code == 200
    response = client.post(
        "/api/v1/brokers",
        json={"agency_name": "Denied", "contact_name": "Sales Write"},
        headers=sales_headers,
    )
    assert response.status_code == 403
    response = client.patch(
        f"/api/v1/brokers/{broker_id}", json={"notes": "denied"}, headers=sales_headers
    )
    assert response.status_code == 403

    buyer = user_factory(role=RoleName.BUYER)
    buyer_headers = auth_headers(buyer.email)
    response = client.get("/api/v1/brokers", headers=buyer_headers)
    assert response.status_code == 403
