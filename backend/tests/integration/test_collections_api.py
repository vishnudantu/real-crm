"""API-level checks for /collections: RBAC gates, tenant isolation, shapes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.leads.models import Lead
from app.modules.postsales import service as postsales_service
from app.modules.postsales.schemas import (
    InstallmentSpec,
    PaymentPlanCreateRequest,
    SaleBookingCreateRequest,
)
from app.modules.projects.models import Project
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from tests.support import TEST_PASSWORD


def _login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _setup(test_session_factory, user_factory, *, slug="api-cc"):
    with test_session_factory() as session:
        tenant = Tenant(slug=slug, name=slug)
        session.add(tenant)
        session.flush()
        admin = user_factory(role=RoleName.ADMIN, tenant=tenant, email=f"admin@{slug}.example")
        sales = user_factory(role=RoleName.SALES_EXECUTIVE, tenant=tenant, email=f"sales@{slug}.example")
        manager = user_factory(role=RoleName.MANAGER, tenant=tenant, email=f"mgr@{slug}.example")
        buyer = user_factory(role=RoleName.BUYER, tenant=tenant, email=f"buyer@{slug}.example")
        project = Project(
            tenant_id=tenant.id, name="Tower", slug=f"t-{slug}", location="Pune",
            status="ACTIVE", created_by=admin.id,
        )
        session.add(project)
        session.flush()
        lead = Lead(
            tenant_id=tenant.id, full_name="Buyer One", email=f"lead@{slug}.example",
            phone="+919811111111", project_id=project.id, source="WEBSITE",
            status="CONVERTED", consent_to_contact=True,
        )
        session.add(lead)
        session.flush()
        booking = postsales_service.create_booking(
            session, actor=admin,
            payload=SaleBookingCreateRequest(
                lead_id=lead.id, unit_number="A-1", consideration_paise=10_000,
            ),
        )
        plan = postsales_service.create_plan(
            session, actor=admin, booking_id=booking.id,
            payload=PaymentPlanCreateRequest(
                name="P", plan_type="CONSTRUCTION_LINKED",
                installments=[InstallmentSpec(
                    milestone="Due", amount_paise=10_000, due_on=date.today(),
                )],
            ),
        )
        session.commit()
        installment_id = plan.installments[0].id  # loaded before session close
        return {
            "tenant": tenant, "admin": admin, "sales": sales, "manager": manager,
            "buyer": buyer, "project": project, "lead": lead,
            "installment_id": installment_id,
        }


def test_collections_api_gates_and_shapes(
    client: TestClient, override_db, seeded_roles, test_session_factory, user_factory,
) -> None:
    data = _setup(test_session_factory, user_factory)
    month = date.today().strftime("%Y-%m")
    admin_h = _login(client, data["admin"].email)
    sales_h = _login(client, data["sales"].email)
    mgr_h = _login(client, data["manager"].email)
    buyer_h = _login(client, data["buyer"].email)

    for headers in (admin_h, sales_h, mgr_h):
        cal = client.get(f"/api/v1/collections/calendar?month={month}", headers=headers)
        assert cal.status_code == 200, cal.text
        body = cal.json()
        assert body["month"] == month
        flat = [r for d in body["days"] for r in d["rows"]]
        assert flat and flat[0]["unit_number"] == "A-1"

        esc = client.get("/api/v1/collections/escalations", headers=headers)
        assert esc.status_code == 200
        assert set(esc.json()["groups"]) == {"warning", "critical", "severe"}

        stats = client.get("/api/v1/collections/stats", headers=headers)
        assert stats.status_code == 200
        assert "recovered_30d_paise" in stats.json()

    # Buyer (not admin/manager/sales) is forbidden from reads.
    denied = client.get(f"/api/v1/collections/calendar?month={month}", headers=buyer_h)
    assert denied.status_code == 403

    # Promise write is admin-only.
    installment_id = data["installment_id"]
    payload = {
        "amount_paise": 5000,
        "promised_on": (date.today() + timedelta(days=2)).isoformat(),
        "note": "Soon",
    }
    forbidden = client.post(
        f"/api/v1/collections/installments/{installment_id}/promises",
        headers=sales_h, json=payload,
    )
    assert forbidden.status_code == 403

    created = client.post(
        f"/api/v1/collections/installments/{installment_id}/promises",
        headers=admin_h, json=payload,
    )
    assert created.status_code == 201, created.text

    listed = client.get(
        f"/api/v1/collections/installments/{installment_id}/promises", headers=sales_h,
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    # Unknown installment => 404 (also covers cross-tenant shape).
    missing = client.post(
        f"/api/v1/collections/installments/{uuid4()}/promises",
        headers=admin_h, json=payload,
    )
    assert missing.status_code == 404


def test_collections_cross_tenant_isolation(
    client: TestClient, override_db, seeded_roles, test_session_factory, user_factory,
) -> None:
    a = _setup(test_session_factory, user_factory, slug="tenant-a")
    b = _setup(test_session_factory, user_factory, slug="tenant-b")
    a_admin = _login(client, a["admin"].email)
    month = date.today().strftime("%Y-%m")

    # Tenant A's calendar never shows tenant B's installment.
    cal = client.get(f"/api/v1/collections/calendar?month={month}", headers=a_admin)
    flat = [r for d in cal.json()["days"] for r in d["rows"]]
    assert len(flat) == 1
    assert flat[0]["installment_id"] == str(a["installment_id"])

    # Tenant A admin cannot attach a promise to tenant B's installment.
    payload = {
        "amount_paise": 100,
        "promised_on": date.today().isoformat(),
        "note": None,
    }
    cross = client.post(
        f"/api/v1/collections/installments/{b['installment_id']}/promises",
        headers=a_admin, json=payload,
    )
    assert cross.status_code == 404


def test_policy_endpoints(
    client: TestClient, override_db, seeded_roles, test_session_factory, user_factory,
) -> None:
    data = _setup(test_session_factory, user_factory, slug="pol-co")
    admin_h = _login(client, data["admin"].email)
    sales_h = _login(client, data["sales"].email)

    got = client.get("/api/v1/collections/policy", headers=sales_h)
    assert got.status_code == 200
    assert got.json()["offsets"] == [-7, 0, 7, 14]

    put = client.put(
        "/api/v1/collections/policy", headers=admin_h,
        json={"offsets": [-3, 0, 5], "channels": ["EMAIL"]},
    )
    assert put.status_code == 200, put.text
    assert put.json()["offsets"] == [-3, 0, 5]
    assert put.json()["channels"] == ["EMAIL"]

    invalid = client.put(
        "/api/v1/collections/policy", headers=admin_h,
        json={"offsets": ["x"]},
    )
    assert invalid.status_code == 422

    # Non-admin cannot write policy.
    denied = client.put(
        "/api/v1/collections/policy", headers=sales_h, json={"offsets": [0]},
    )
    assert denied.status_code == 403
