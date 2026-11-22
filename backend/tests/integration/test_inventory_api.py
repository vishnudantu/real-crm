"""API-level checks: inventory routing, RBAC, response shapes, 404 isolation."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.inventory import repository
from app.modules.inventory.models import UnitStatus
from app.modules.leads.models import Lead
from app.modules.projects.models import Project
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from tests.support import TEST_PASSWORD


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _setup(
    test_session_factory: sessionmaker[Session],
    user_factory: Callable[..., User],
) -> tuple[Tenant, User, User, Project, Lead]:
    
    with test_session_factory() as session:
        tenant = Tenant(slug="api-inv", name="API Inventory Co")
        session.add(tenant)
        session.flush()
        admin = user_factory(role=RoleName.ADMIN, tenant=tenant, email="admin@api-inv.example")
        sales = user_factory(role=RoleName.SALES_EXECUTIVE, tenant=tenant, email="sales@api-inv.example")
        project = Project(
            tenant_id=tenant.id, name="API Tower", slug="api-tower", location="Pune",
            status="ACTIVE", created_by=admin.id,
        )
        session.add(project)
        session.flush()
        lead = Lead(
            tenant_id=tenant.id, full_name="Buyer", email="buyer@api-inv.example",
            phone="+919812345678", project_id=project.id, source="WEBSITE",
            status="CONVERTED", consent_to_contact=True,
        )
        session.add(lead)
        session.commit()
        return tenant, admin, sales, project, lead


def test_inventory_end_to_end_over_api(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    user_factory: Callable[..., User],
) -> None:
    tenant, admin, sales, project, lead = _setup(test_session_factory, user_factory)
    admin_headers = _login(client, "admin@api-inv.example", TEST_PASSWORD)
    sales_headers = _login(client, "sales@api-inv.example", TEST_PASSWORD)

    # Admin creates a unit directly AVAILABLE.
    created = client.post(
        "/api/v1/inventory/units",
        headers=admin_headers,
        json={"project_id": str(project.id), "internal_code": "A-1204", "configuration": "3 BHK",
              "carpet_area_sqft": 1450, "status": "AVAILABLE"},
    )
    assert created.status_code == 201, created.text
    unit_id = created.json()["id"]
    assert created.json()["internal_code"] == "A-1204"
    assert created.json()["rera_disclosure_json"] == {}

    # Sales executive may not create units.
    forbidden = client.post(
        "/api/v1/inventory/units",
        headers=sales_headers,
        json={"project_id": str(project.id), "internal_code": "B-1"},
    )
    assert forbidden.status_code == 403

    # Bulk with a collision: per-row reasons, no partial commit for the bad row.
    bulk = client.post(
        "/api/v1/inventory/units/bulk?dry_run=false",
        headers=admin_headers,
        json={"rows": [
            {"project_id": str(project.id), "internal_code": "A-1204"},
            {"project_id": str(project.id), "internal_code": "A-1205"},
        ]},
    )
    assert bulk.status_code == 200, bulk.text
    body = bulk.json()
    assert body["created"] == 1 and body["failed"] == 1
    assert body["results"][0]["ok"] is False
    assert body["results"][1]["ok"] is True

    listing = client.get(f"/api/v1/inventory/units?project_id={project.id}", headers=admin_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 2

    # Sales executive acquires a hold on the unit.
    held = client.post(
        "/api/v1/inventory/holds",
        headers=sales_headers,
        json={"unit_id": unit_id, "lead_id": str(lead.id), "hours": 48, "reason": "Hot lead"},
    )
    assert held.status_code == 201, held.text
    hold_id = held.json()["id"]
    assert held.json()["state"] == "ACTIVE"

    # Second hold is 409.
    again = client.post(
        "/api/v1/inventory/holds",
        headers=sales_headers,
        json={"unit_id": unit_id, "lead_id": str(lead.id)},
    )
    assert again.status_code == 409

    # Extend twice, then the limit trips.
    for _ in range(2):
        extended = client.post(f"/api/v1/inventory/holds/{hold_id}/extend", headers=sales_headers, json={"hours": 12})
        assert extended.status_code == 200, extended.text
    third = client.post(f"/api/v1/inventory/holds/{hold_id}/extend", headers=sales_headers, json={"hours": 12})
    assert third.status_code == 409

    # Detail includes status history.
    detail = client.get(f"/api/v1/inventory/units/{unit_id}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == "ON_HOLD"
    assert [e["to_status"] for e in detail.json()["status_history"]] == ["ON_HOLD"]
    assert detail.json()["status_history"][0]["event_meta"]["hold_id"] == hold_id

    availability = client.get(f"/api/v1/inventory/availability/{project.id}", headers=sales_headers)
    assert availability.status_code == 200
    assert availability.json()["counts"]["ON_HOLD"] == 1
    assert availability.json()["counts"]["DRAFT"] == 1  # bulk-created A-1205 defaults to DRAFT
    assert availability.json()["counts"]["AVAILABLE"] == 0

    # Convert: booking id returned, hold CONVERTED, unit BOOKED.
    converted = client.post(
        f"/api/v1/inventory/holds/{hold_id}/convert",
        headers=sales_headers,
        json={"consideration_paise": 15000000},
    )
    assert converted.status_code == 200, converted.text
    booking_id = converted.json()["booking_id"]
    assert converted.json()["hold"]["state"] == "CONVERTED"
    assert converted.json()["hold"]["converted_booking_id"] == booking_id

    with test_session_factory() as session:
        from app.modules.postsales.models import SaleBooking
        booking = session.get(SaleBooking, UUID(booking_id))
        assert booking.unit_id == UUID(unit_id)
        assert booking.unit_number == "A-1204"

    booked_detail = client.get(f"/api/v1/inventory/units/{unit_id}", headers=admin_headers)
    assert booked_detail.json()["status"] == "BOOKED"


def test_release_flow_over_api(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    user_factory: Callable[..., User],
) -> None:
    tenant, admin, sales, project, lead = _setup(test_session_factory, user_factory)
    admin_headers = _login(client, "admin@api-inv.example", TEST_PASSWORD)
    sales_headers = _login(client, "sales@api-inv.example", TEST_PASSWORD)

    created = client.post(
        "/api/v1/inventory/units", headers=admin_headers,
        json={"project_id": str(project.id), "internal_code": "R-1", "status": "AVAILABLE"},
    )
    unit_id = created.json()["id"]
    held = client.post(
        "/api/v1/inventory/holds", headers=sales_headers,
        json={"unit_id": unit_id, "lead_id": str(lead.id)},
    )
    hold_id = held.json()["id"]
    released = client.post(
        f"/api/v1/inventory/holds/{hold_id}/release", headers=sales_headers,
        json={"reason": "Buyer changed mind"},
    )
    assert released.status_code == 200, released.text
    assert released.json()["state"] == "RELEASED"
    assert released.json()["release_source"] == "MANUAL"

    re_held = client.post(
        "/api/v1/inventory/holds", headers=sales_headers,
        json={"unit_id": unit_id, "lead_id": str(lead.id)},
    )
    assert re_held.status_code == 201

    illegal = client.patch(
        f"/api/v1/inventory/units/{unit_id}/status", headers=admin_headers,
        json={"to_status": "SOLD", "reason": "skip everything"},
    )
    assert illegal.status_code == 409

    sales_forbidden = client.patch(
        f"/api/v1/inventory/units/{unit_id}/status", headers=sales_headers,
        json={"to_status": "BLOCKED", "approved": True},
    )
    assert sales_forbidden.status_code == 403


def test_cross_tenant_read_is_404_over_api(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    user_factory: Callable[..., User],
) -> None:
    tenant, admin, sales, project, lead = _setup(test_session_factory, user_factory)
    admin_headers = _login(client, "admin@api-inv.example", TEST_PASSWORD)

    other_tenant = Tenant(slug="other-inv", name="Other Co")
    with test_session_factory() as session:
        session.add(other_tenant)
        session.flush()
        other_admin = user_factory(role=RoleName.ADMIN, tenant=other_tenant, email="other@other-inv.example")
    other_headers = _login(client, "other@other-inv.example", TEST_PASSWORD)

    created = client.post(
        "/api/v1/inventory/units", headers=admin_headers,
        json={"project_id": str(project.id), "internal_code": "X-1", "status": "AVAILABLE"},
    )
    unit_id = created.json()["id"]

    read_other = client.get(f"/api/v1/inventory/units/{unit_id}", headers=other_headers)
    assert read_other.status_code == 404
    avail_other = client.get(f"/api/v1/inventory/availability/{project.id}", headers=other_headers)
    assert avail_other.status_code == 404
    hold_other = client.post(
        "/api/v1/inventory/holds", headers=other_headers, json={"unit_id": unit_id}
    )
    assert hold_other.status_code == 404
    create_other = client.post(
        "/api/v1/inventory/units", headers=other_headers,
        json={"project_id": str(project.id), "internal_code": "Y-1"},
    )
    assert create_other.status_code == 404
