"""Integration tests for solar-facing endpoints."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.projects.models import Project, ProjectFact, FactStatus
from app.modules.solar.models import TowerOrientation
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from tests.support import TEST_PASSWORD


def _login(client: TestClient, email: str, password: str = TEST_PASSWORD) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
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
    """Set up a tenant with admin, sales, project, and tower orientation."""
    admin = user_factory(role=RoleName.ADMIN)
    other_tenant = Tenant(slug=f"solar-other-{uuid4().hex[:8]}", name="Other Builder")
    with test_session_factory() as session:
        session.add(other_tenant)
        session.commit()
    outsider = user_factory(role=RoleName.ADMIN, tenant=other_tenant)
    sales = user_factory(role=RoleName.SALES_EXECUTIVE)

    with test_session_factory() as session:
        project = Project(
            tenant_id=admin.tenant_id,
            name="Solar Towers",
            slug=f"solar-{uuid4().hex[:8]}",
            location="Hyderabad",
            status="ACTIVE",
            created_by=admin.id,
            latitude=17.38,
            longitude=78.48,
        )
        foreign_project = Project(
            tenant_id=outsider.tenant_id,
            name="Foreign Towers",
            slug=f"foreign-solar-{uuid4().hex[:8]}",
            location="Hyderabad",
            status="ACTIVE",
            created_by=outsider.id,
            latitude=17.38,
            longitude=78.48,
        )
        session.add_all([project, foreign_project])
        session.commit()

        return {
            "factory": test_session_factory,
            "tenant_id": admin.tenant_id,
            "admin_id": admin.id,
            "admin_email": admin.email,
            "headers": auth_headers(admin.email),
            "foreign_headers": auth_headers(outsider.email),
            "sales_headers": auth_headers(sales.email),
            "project_id": project.id,
            "foreign_project_id": foreign_project.id,
        }


def _create_unit(client: TestClient, headers: dict, project_id: UUID, **overrides) -> dict:
    payload = {
        "project_id": str(project_id),
        "internal_code": f"A-{uuid4().hex[:6]}",
        "tower": "T1",
        "facing_deg": 90.0,
        "status": "AVAILABLE",
    }
    payload.update(overrides)
    response = client.post("/api/v1/inventory/units", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


class TestUpdateCoordinates:
    def test_admin_can_set_coordinates(self, client: TestClient, env: dict) -> None:
        response = client.patch(
            f"/api/v1/solar/projects/{env['project_id']}/coordinates",
            json={"latitude": 17.38, "longitude": 78.48},
            headers=env["headers"],
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["latitude"] == 17.38
        assert body["longitude"] == 78.48

    def test_sales_cannot_set_coordinates(self, client: TestClient, env: dict) -> None:
        response = client.patch(
            f"/api/v1/solar/projects/{env['project_id']}/coordinates",
            json={"latitude": 17.38, "longitude": 78.48},
            headers=env["sales_headers"],
        )
        assert response.status_code == 403

    def test_cross_tenant_coordinates_404(self, client: TestClient, env: dict) -> None:
        response = client.patch(
            f"/api/v1/solar/projects/{env['project_id']}/coordinates",
            json={"latitude": 17.38, "longitude": 78.48},
            headers=env["foreign_headers"],
        )
        assert response.status_code == 404

    def test_invalid_latitude(self, client: TestClient, env: dict) -> None:
        response = client.patch(
            f"/api/v1/solar/projects/{env['project_id']}/coordinates",
            json={"latitude": 91.0, "longitude": 78.48},
            headers=env["headers"],
        )
        assert response.status_code == 422


class TestTowerOrientation:
    def test_admin_can_upsert_tower(self, client: TestClient, env: dict) -> None:
        response = client.put(
            "/api/v1/solar/tower-orientation",
            json={
                "project_id": str(env["project_id"]),
                "tower_label": "T1",
                "orientation_deg": 90.0,
            },
            headers=env["headers"],
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["tower_label"] == "T1"
        assert body["orientation_deg"] == 90.0

    def test_upsert_updates_existing(self, client: TestClient, env: dict) -> None:
        # Create.
        client.put(
            "/api/v1/solar/tower-orientation",
            json={
                "project_id": str(env["project_id"]),
                "tower_label": "T1",
                "orientation_deg": 90.0,
            },
            headers=env["headers"],
        )
        # Update.
        response = client.put(
            "/api/v1/solar/tower-orientation",
            json={
                "project_id": str(env["project_id"]),
                "tower_label": "T1",
                "orientation_deg": 180.0,
            },
            headers=env["headers"],
        )
        assert response.status_code == 200
        assert response.json()["orientation_deg"] == 180.0

    def test_cross_tenant_tower_404(self, client: TestClient, env: dict) -> None:
        response = client.put(
            "/api/v1/solar/tower-orientation",
            json={
                "project_id": str(env["project_id"]),
                "tower_label": "T1",
                "orientation_deg": 90.0,
            },
            headers=env["foreign_headers"],
        )
        assert response.status_code == 404


class TestSunPath:
    def test_get_sun_path(self, client: TestClient, env: dict) -> None:
        response = client.get(
            f"/api/v1/solar/projects/{env['project_id']}/sun-path",
            headers=env["headers"],
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["latitude"] == 17.38
        assert body["longitude"] == 78.48
        assert len(body["solstices_and_equinox"]) == 4
        for day in body["solstices_and_equinox"]:
            assert "sunrise" in day
            assert "sunset" in day
            assert "solar_noon" in day
            assert day["day_length_hours"] > 0

    def test_sales_can_read_sun_path(self, client: TestClient, env: dict) -> None:
        response = client.get(
            f"/api/v1/solar/projects/{env['project_id']}/sun-path",
            headers=env["sales_headers"],
        )
        assert response.status_code == 200

    def test_cross_tenant_sun_path_404(self, client: TestClient, env: dict) -> None:
        response = client.get(
            f"/api/v1/solar/projects/{env['project_id']}/sun-path",
            headers=env["foreign_headers"],
        )
        assert response.status_code == 404


class TestUnitSunScore:
    def test_unit_with_facing_deg(self, client: TestClient, env: dict) -> None:
        unit = _create_unit(client, env["headers"], env["project_id"], facing_deg=90.0)
        response = client.get(
            f"/api/v1/solar/units/{unit['id']}/sun-score",
            headers=env["headers"],
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["facing_label"] == "E"
        assert body["exposure_class"] == "morning"
        assert body["comfort_score"] >= 80
        assert "traditionally preferred" in body["vastu_note"].lower()
        assert body["pricing_premium_min_pct"] >= 0

    def test_unit_falls_back_to_tower(self, client: TestClient, env: dict) -> None:
        # Set tower orientation.
        client.put(
            "/api/v1/solar/tower-orientation",
            json={
                "project_id": str(env["project_id"]),
                "tower_label": "T1",
                "orientation_deg": 270.0,
            },
            headers=env["headers"],
        )
        # Create unit without facing_deg but with tower.
        unit = _create_unit(
            client, env["headers"], env["project_id"], facing_deg=None, tower="T1"
        )
        response = client.get(
            f"/api/v1/solar/units/{unit['id']}/sun-score",
            headers=env["headers"],
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["facing_label"] == "W"
        assert body["exposure_class"] == "afternoon"

    def test_cross_tenant_unit_404(self, client: TestClient, env: dict) -> None:
        unit = _create_unit(client, env["headers"], env["project_id"])
        response = client.get(
            f"/api/v1/solar/units/{unit['id']}/sun-score",
            headers=env["foreign_headers"],
        )
        assert response.status_code == 404


class TestGenerateFacts:
    def test_generate_facts_creates_drafts(self, client: TestClient, env: dict) -> None:
        # Set tower orientation first.
        client.put(
            "/api/v1/solar/tower-orientation",
            json={
                "project_id": str(env["project_id"]),
                "tower_label": "T1",
                "orientation_deg": 90.0,
            },
            headers=env["headers"],
        )
        response = client.post(
            f"/api/v1/solar/projects/{env['project_id']}/generate-facts",
            headers=env["headers"],
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["generated"] == 2
        assert body["status"] == "DRAFT"

        # Verify facts are DRAFT in the database.
        with env["factory"]() as session:
            facts = session.scalars(
                select(ProjectFact).where(
                    ProjectFact.tenant_id == env["tenant_id"],
                    ProjectFact.project_id == env["project_id"],
                )
            ).all()
            assert len(facts) >= 2
            for fact in facts:
                assert fact.status == FactStatus.DRAFT.value

    def test_generate_facts_idempotent(self, client: TestClient, env: dict) -> None:
        # Generate twice — should update existing drafts.
        for _ in range(2):
            response = client.post(
                f"/api/v1/solar/projects/{env['project_id']}/generate-facts",
                headers=env["headers"],
            )
            assert response.status_code == 200

        with env["factory"]() as session:
            facts = session.scalars(
                select(ProjectFact).where(
                    ProjectFact.tenant_id == env["tenant_id"],
                    ProjectFact.project_id == env["project_id"],
                    ProjectFact.status == FactStatus.DRAFT.value,
                )
            ).all()
            # Should have exactly 2 draft facts (not duplicated).
            assert len(facts) == 2

    def test_cross_tenant_generate_404(self, client: TestClient, env: dict) -> None:
        response = client.post(
            f"/api/v1/solar/projects/{env['project_id']}/generate-facts",
            headers=env["foreign_headers"],
        )
        assert response.status_code == 404

    def test_sales_cannot_generate(self, client: TestClient, env: dict) -> None:
        response = client.post(
            f"/api/v1/solar/projects/{env['project_id']}/generate-facts",
            headers=env["sales_headers"],
        )
        assert response.status_code == 403
