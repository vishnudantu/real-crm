"""Integration tests for Advanced Inventory Intelligence (Module 20)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.inventory.models import PropertyUnit, UnitHold, UnitStatus
from app.modules.leads.models import Lead
from app.modules.postsales.models import SaleBooking
from app.modules.projects.models import Project
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from tests.support import TEST_PASSWORD


def _login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def env(
    client: TestClient,
    override_db: None,
    test_session_factory: sessionmaker[Session],
    user_factory: Callable[..., User],
    auth_headers,
) -> dict:
    admin = user_factory(role=RoleName.ADMIN)
    other_tenant = Tenant(slug=f"ii-other-{uuid4().hex[:8]}", name="Other Builder")
    with test_session_factory() as session:
        session.add(other_tenant)
        session.commit()
    outsider = user_factory(role=RoleName.ADMIN, tenant=other_tenant)

    with test_session_factory() as session:
        project = Project(
            tenant_id=admin.tenant_id,
            name="Intelligence Towers",
            slug=f"ii-{uuid4().hex[:8]}",
            location="Hyderabad",
            status="ACTIVE",
            created_by=admin.id,
        )
        session.add(project)
        session.flush()

        now = datetime.now(UTC)
        old = now - timedelta(days=200)
        units = [
            PropertyUnit(
                tenant_id=admin.tenant_id,
                project_id=project.id,
                internal_code="A-101",
                configuration="3 BHK",
                tower="A",
                floor="1",
                facing="E",
                status=UnitStatus.AVAILABLE.value,
                created_at=old,
            ),
            PropertyUnit(
                tenant_id=admin.tenant_id,
                project_id=project.id,
                internal_code="A-102",
                configuration="3 BHK",
                tower="A",
                floor="2",
                facing="E",
                status=UnitStatus.AVAILABLE.value,
                created_at=now - timedelta(days=10),
            ),
            PropertyUnit(
                tenant_id=admin.tenant_id,
                project_id=project.id,
                internal_code="B-201",
                configuration="2 BHK",
                tower="B",
                floor="2",
                facing="W",
                status=UnitStatus.SOLD.value,
                created_at=old,
            ),
            PropertyUnit(
                tenant_id=admin.tenant_id,
                project_id=project.id,
                internal_code="B-202",
                configuration="2 BHK",
                tower="B",
                floor="3",
                facing="W",
                status=UnitStatus.ON_HOLD.value,
                created_at=now - timedelta(days=5),
            ),
        ]
        session.add_all(units)
        session.flush()

        # A booking giving B-201 its booked value (requires a lead + project).
        lead = Lead(
            tenant_id=admin.tenant_id,
            full_name="Booking Lead",
            email=f"lead-{uuid4().hex[:8]}@example.com",
            project_id=project.id,
            source="WEBSITE",
            status="CONVERTED",
            consent_to_contact=True,
        )
        session.add(lead)
        session.flush()
        sold = next(u for u in units if u.internal_code == "B-201")
        booking = SaleBooking(
            tenant_id=admin.tenant_id,
            lead_id=lead.id,
            project_id=project.id,
            unit_id=sold.id,
            unit_number="B-201",
            consideration_paise=15_000_000,
            booked_on=now.date(),
        )
        session.add(booking)

        # An ACTIVE hold on B-202 expiring soon (HIGH risk).
        held = next(u for u in units if u.internal_code == "B-202")
        hold = UnitHold(
            tenant_id=admin.tenant_id,
            unit_id=held.id,
            owner_user_id=admin.id,
            state="ACTIVE",
            expires_at=now + timedelta(hours=3),
            extension_count=0,
        )
        session.add(hold)
        session.commit()

        return {
            "tenant_id": admin.tenant_id,
            "headers": auth_headers(admin.email),
            "foreign_headers": auth_headers(outsider.email),
            "project_id": project.id,
            "requested_unit_id": next(u for u in units if u.internal_code == "A-101").id,
            "sold_unit_code": "B-201",
        }


def test_revenue_map(client: TestClient, env: dict) -> None:
    response = client.get(
        f"/api/v1/inventory/intelligence/projects/{env['project_id']}/revenue-map",
        headers=env["headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_units"] == 4
    assert body["by_status"]["AVAILABLE"] == 2
    assert body["by_status"]["SOLD"] == 1
    assert body["total_booked_value_paise"] == 15_000_000
    assert body["oldest_unit_age_days"] >= 199
    assert len(body["rows"]) == 4


def test_hold_expiry_flags_active_hold(client: TestClient, env: dict) -> None:
    response = client.get(
        f"/api/v1/inventory/intelligence/projects/{env['project_id']}/hold-expiry",
        headers=env["headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["risk"] == "HIGH"
    assert body["items"][0]["hours_remaining"] <= 6


def test_unsold_risk_only_available(client: TestClient, env: dict) -> None:
    response = client.get(
        f"/api/v1/inventory/intelligence/projects/{env['project_id']}/unsold-risk",
        headers=env["headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # Only the two AVAILABLE units are scored.
    assert body["total"] == 2
    risks = {item["internal_code"]: item["risk"] for item in body["items"]}
    assert risks["A-101"] == "HIGH"  # ~200 days available
    assert risks["A-102"] == "LOW"  # ~10 days available


def test_conflicts_clean_inventory(client: TestClient, env: dict) -> None:
    response = client.get(
        f"/api/v1/inventory/intelligence/projects/{env['project_id']}/conflicts",
        headers=env["headers"],
    )
    assert response.status_code == 200, response.text
    # The seeded inventory has no inconsistent states.
    assert response.json()["total"] == 0


def test_recommendations_for_unavailable_unit(client: TestClient, env: dict) -> None:
    # Request recommendations for the requested unit A-101: alternatives should
    # be AVAILABLE units in the same project, never the sold unit B-201.
    response = client.get(
        f"/api/v1/inventory/intelligence/units/{env['requested_unit_id']}/recommendations",
        headers=env["headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert item["internal_code"] != "B-201"
    # A-102 shares configuration + tower + facing with requested A-101.
    top = body["items"][0]
    assert "same configuration" in top["reasons"]


def test_cross_tenant_project_returns_404(client: TestClient, env: dict) -> None:
    response = client.get(
        f"/api/v1/inventory/intelligence/projects/{env['project_id']}/revenue-map",
        headers=env["foreign_headers"],
    )
    assert response.status_code == 404


def test_cross_tenant_unit_recommendations_404(client: TestClient, env: dict) -> None:
    response = client.get(
        f"/api/v1/inventory/intelligence/units/{env['requested_unit_id']}/recommendations",
        headers=env["foreign_headers"],
    )
    assert response.status_code == 404
