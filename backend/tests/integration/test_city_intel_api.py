"""Integration tests for City Intelligence Engine (Phase 1)."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.leads.models import Lead
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
    sales = user_factory(role=RoleName.SALES_EXECUTIVE)
    other_tenant = Tenant(slug=f"ci-other-{uuid4().hex[:8]}", name="Other Builder")
    with test_session_factory() as session:
        session.add(other_tenant)
        session.commit()
    outsider = user_factory(role=RoleName.ADMIN, tenant=other_tenant)

    with test_session_factory() as session:
        project = Project(
            tenant_id=admin.tenant_id,
            name="Skyline",
            slug=f"ci-{uuid4().hex[:8]}",
            location="Financial District, Hyderabad",
            status="ACTIVE",
            created_by=admin.id,
            latitude=17.38,
            longitude=78.48,
        )
        session.add(project)
        session.flush()
        for idx in range(3):
            session.add(
                Lead(
                    tenant_id=admin.tenant_id,
                    full_name=f"Lead {idx}",
                    email=f"lead{idx}-{uuid4().hex[:6]}@example.com",
                    project_id=project.id,
                    source="WEBSITE",
                    status="CONVERTED" if idx == 0 else "NEW",
                    budget_min=8_000_000,
                    budget_max=12_000_000,
                    preferred_configuration="3 BHK",
                    consent_to_contact=True,
                )
            )
        session.commit()
        return {
            "tenant_id": admin.tenant_id,
            "headers": auth_headers(admin.email),
            "sales_headers": auth_headers(sales.email),
            "foreign_headers": auth_headers(outsider.email),
            "project_id": project.id,
        }


def test_demand_endpoint(client: TestClient, env: dict) -> None:
    response = client.get("/api/v1/city-intel/demand", headers=env["headers"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] >= 1
    mine = next(r for r in body["items"] if r["project_id"] == str(env["project_id"]))
    assert mine["lead_count"] == 3
    assert mine["locality"] == "Financial District, Hyderabad"
    assert mine["top_property_type"] == "3 BHK"


def test_add_and_list_amenities_and_connectivity(client: TestClient, env: dict) -> None:
    create = client.post(
        "/api/v1/city-intel/amenities",
        headers=env["headers"],
        json={
            "project_id": str(env["project_id"]),
            "category": "transit",
            "name": "Raidurg Metro",
            "distance_km": 1.2,
            "travel_minutes": 5,
            "confidence": "verified",
            "source_ref": "HMRL phase 2",
        },
    )
    assert create.status_code == 201, create.text

    listing = client.get(
        f"/api/v1/city-intel/projects/{env['project_id']}/amenities", headers=env["headers"]
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["confidence"] == "verified"

    connectivity = client.get(
        f"/api/v1/city-intel/projects/{env['project_id']}/connectivity", headers=env["headers"]
    )
    assert connectivity.status_code == 200, connectivity.text
    body = connectivity.json()
    assert body["score"] > 0
    transit = next(c for c in body["by_category"] if c["category"] == "transit")
    assert transit["count"] == 1
    assert transit["nearest_km"] == 1.2


def test_locality_report_create_list_and_facts(client: TestClient, env: dict) -> None:
    create = client.post(
        "/api/v1/city-intel/reports",
        headers=env["headers"],
        json={
            "project_id": str(env["project_id"]),
            "title": "Financial District outlook",
            "body": "Sustained demand from nearby employment hubs.",
            "sources": [
                {"label": "Local brokerage survey", "confidence": "estimated", "observed_on": "2026-11-01"}
            ],
            "as_of": "2026-11-01",
        },
    )
    assert create.status_code == 201, create.text
    assert create.json()["status"] == "DRAFT"
    assert create.json()["sources"][0]["confidence"] == "estimated"

    listing = client.get(
        f"/api/v1/city-intel/projects/{env['project_id']}/reports", headers=env["headers"]
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    gen = client.post(
        f"/api/v1/city-intel/projects/{env['project_id']}/generate-facts", headers=env["headers"]
    )
    assert gen.status_code == 200, gen.text
    assert gen.json()["status"] == "DRAFT"
    assert gen.json()["generated"] >= 2  # demand + report (no amenities in this test's project)


def test_sales_can_read_but_not_curate(client: TestClient, env: dict) -> None:
    read = client.get("/api/v1/city-intel/demand", headers=env["sales_headers"])
    assert read.status_code == 200
    write = client.post(
        "/api/v1/city-intel/amenities",
        headers=env["sales_headers"],
        json={"project_id": str(env["project_id"]), "category": "school", "name": "X"},
    )
    assert write.status_code == 403


def test_cross_tenant_project_is_404(client: TestClient, env: dict) -> None:
    response = client.get(
        f"/api/v1/city-intel/projects/{env['project_id']}/amenities", headers=env["foreign_headers"]
    )
    assert response.status_code == 404


def test_invalid_amenity_confidence_rejected(client: TestClient, env: dict) -> None:
    response = client.post(
        "/api/v1/city-intel/amenities",
        headers=env["headers"],
        json={"project_id": str(env["project_id"]), "category": "school", "name": "X", "confidence": "certain"},
    )
    assert response.status_code == 422
