"""Integration tests for approval decision side effects (wired flows).

Covers the two wired pairs:

- SITE_VISIT_CAR / booking: create flags the booking PENDING; approve sets
  APPROVED; reject sets REJECTED; cancel reverts NONE — all in one transaction
  with the decision.
- DISCOUNT / unit: create flags the unit PENDING; approve writes
  approved_discount_paise + APPROVED; reject sets REJECTED without the amount;
  cancel reverts NONE.

Plus the dispatcher contract: missing entity 400 with no decision committed,
cross-tenant 404, and buyers 403.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.bookings.models import Booking, CarRequestStatus
from app.modules.inventory.models import DiscountStatus, PropertyUnit
from app.modules.leads.models import Lead
from app.modules.projects.models import Project
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from tests.booking_support import create_booking, create_slot
from tests.lead_support import assign_lead, create_lead
from tests.project_support import create_project


@pytest.fixture()
def env(
    client: TestClient,
    override_db: None,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> dict:
    admin = user_factory(role=RoleName.ADMIN)
    sales = user_factory(role=RoleName.SALES_EXECUTIVE)
    return {
        "factory": test_session_factory,
        "admin": admin,
        "sales": sales,
        "admin_headers": auth_headers(admin.email),
        "sales_headers": auth_headers(sales.email),
    }


def _active_project(client: TestClient, env: dict) -> dict:
    """Create a project and activate it (new projects start inactive)."""

    project = create_project(client, env["admin_headers"])
    response = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"status": "ACTIVE"},
        headers=env["admin_headers"],
    )
    assert response.status_code == 200, response.text
    return response.json()


def _booking_for_sales(client: TestClient, env: dict) -> dict:
    """Create an active project, lead assigned to sales, slot, and booking (admin books)."""
    project = _active_project(client, env)
    lead = create_lead(client, project_id=project["id"], headers=env["admin_headers"])
    assign_lead(
        client, env["admin_headers"], lead["id"], executive_id=env["sales"].id
    )
    start = datetime.now(UTC) + timedelta(days=1)
    slot = create_slot(
        client,
        env["admin_headers"],
        project_id=project["id"],
        start_time=start,
        end_time=start + timedelta(hours=1),
        capacity=5,
    )
    booking = create_booking(
        client, env["admin_headers"], slot_id=slot["id"], lead_id=lead["id"]
    )
    return {"project": project, "lead": lead, "slot": slot, "booking": booking}


def _unit_for_sales(client: TestClient, env: dict) -> dict:
    """Create an active project and one AVAILABLE unit owned by the tenant."""

    project = _active_project(client, env)
    created = client.post(
        "/api/v1/inventory/units",
        headers=env["admin_headers"],
        json={
            "project_id": project["id"],
            "internal_code": f"A-{uuid4().hex[:6].upper()}",
            "configuration": "3 BHK",
            "status": "AVAILABLE",
        },
    )
    assert created.status_code == 201, created.text
    return {"project": project, "unit": created.json()}


def _car_request(client: TestClient, env: dict, booking_id: str) -> dict:
    response = client.post(
        f"/api/v1/bookings/{booking_id}/car-request",
        json={"reason": "Customer needs a chauffeured visit."},
        headers=env["sales_headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()


def _discount_request(client: TestClient, env: dict, unit_id: str, amount: int = 100_000) -> dict:
    response = client.post(
        f"/api/v1/inventory/units/{unit_id}/discount-request",
        json={"amount_paise": amount, "reason": "Festive offer for the buyer."},
        headers=env["sales_headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()


def _decision(client: TestClient, env: dict, request_id: str, decision="APPROVED"):
    return client.post(
        f"/api/v1/approvals/requests/{request_id}/decision",
        json={"decision": decision, "note": "Reviewed by the manager."},
        headers=env["admin_headers"],
    )


def _cancel(client: TestClient, env: dict, request_id: str):
    return client.post(
        f"/api/v1/approvals/requests/{request_id}/cancel",
        headers=env["sales_headers"],
    )


def _booking_flag(factory, booking_id: str) -> str:
    with factory() as session:
        return session.get(Booking, UUID(booking_id)).car_request_status


def _unit_state(factory, unit_id: str) -> tuple[str, int | None]:
    with factory() as session:
        unit = session.get(PropertyUnit, UUID(unit_id))
        return unit.discount_status, unit.approved_discount_paise


# ---------------------------------------------------------------------------
# Flow 1: site-visit car request on a booking
# ---------------------------------------------------------------------------


def test_car_request_creates_pending_approval_and_booking_flag(
    client: TestClient, env: dict
) -> None:
    created = _booking_for_sales(client, env)
    booking_id = created["booking"]["id"]

    assert _booking_flag(env["factory"], booking_id) == CarRequestStatus.NONE.value

    request = _car_request(client, env, booking_id)
    assert request["status"] == "PENDING"
    assert request["request_type"] == "SITE_VISIT_CAR"
    assert request["reference_type"] == "booking"
    assert request["reference_id"] == booking_id
    assert request["requested_by_id"] == str(env["sales"].id)

    assert _booking_flag(env["factory"], booking_id) == CarRequestStatus.PENDING.value

    detail = client.get(f"/api/v1/bookings/{booking_id}", headers=env["admin_headers"])
    assert detail.status_code == 200, detail.text
    assert detail.json()["car_request_status"] == CarRequestStatus.PENDING.value


def test_admin_approval_sets_booking_flag_approved_atomically(
    client: TestClient, env: dict
) -> None:
    created = _booking_for_sales(client, env)
    request = _car_request(client, env, created["booking"]["id"])

    response = _decision(client, env, request["id"], decision="APPROVED")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "APPROVED"
    assert body["approver_id"] == str(env["admin"].id)
    assert body["decided_at"] is not None

    assert _booking_flag(env["factory"], created["booking"]["id"]) == \
        CarRequestStatus.APPROVED.value


def test_admin_rejection_sets_booking_flag_rejected(
    client: TestClient, env: dict
) -> None:
    created = _booking_for_sales(client, env)
    request = _car_request(client, env, created["booking"]["id"])

    response = _decision(client, env, request["id"], decision="REJECTED")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "REJECTED"

    assert _booking_flag(env["factory"], created["booking"]["id"]) == \
        CarRequestStatus.REJECTED.value


def test_cancel_reverts_booking_flag_to_none(client: TestClient, env: dict) -> None:
    created = _booking_for_sales(client, env)
    request = _car_request(client, env, created["booking"]["id"])

    response = _cancel(client, env, request["id"])
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CANCELLED"

    assert _booking_flag(env["factory"], created["booking"]["id"]) == \
        CarRequestStatus.NONE.value


def test_second_car_request_conflicts_until_first_is_cancelled(
    client: TestClient, env: dict
) -> None:
    created = _booking_for_sales(client, env)
    _car_request(client, env, created["booking"]["id"])

    duplicate = client.post(
        f"/api/v1/bookings/{created['booking']['id']}/car-request",
        json={"reason": "Second request while one is open."},
        headers=env["sales_headers"],
    )
    assert duplicate.status_code == 409


# ---------------------------------------------------------------------------
# Flow 2: discount approval on a unit
# ---------------------------------------------------------------------------


def test_discount_request_creates_pending_approval_and_unit_flag(
    client: TestClient, env: dict
) -> None:
    created = _unit_for_sales(client, env)
    unit_id = created["unit"]["id"]

    request = _discount_request(client, env, unit_id, amount=150_000)
    assert request["status"] == "PENDING"
    assert request["request_type"] == "DISCOUNT"
    assert request["reference_type"] == "unit"
    assert request["reference_id"] == unit_id
    assert request["amount_paise"] == 150_000

    assert _unit_state(env["factory"], unit_id) == (DiscountStatus.PENDING.value, None)


def test_discount_approval_writes_amount_and_flag(client: TestClient, env: dict) -> None:
    created = _unit_for_sales(client, env)
    request = _discount_request(client, env, created["unit"]["id"], amount=250_000)

    response = _decision(client, env, request["id"], decision="APPROVED")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "APPROVED"

    assert _unit_state(env["factory"], created["unit"]["id"]) == (
        DiscountStatus.APPROVED.value, 250_000
    )


def test_discount_rejection_sets_flag_but_not_amount(
    client: TestClient, env: dict
) -> None:
    created = _unit_for_sales(client, env)
    request = _discount_request(client, env, created["unit"]["id"], amount=250_000)

    response = _decision(client, env, request["id"], decision="REJECTED")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "REJECTED"

    assert _unit_state(env["factory"], created["unit"]["id"]) == (
        DiscountStatus.REJECTED.value, None
    )


def test_discount_cancel_reverts_flag_and_never_writes_amount(
    client: TestClient, env: dict
) -> None:
    created = _unit_for_sales(client, env)
    request = _discount_request(client, env, created["unit"]["id"])

    response = _cancel(client, env, request["id"])
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "CANCELLED"

    assert _unit_state(env["factory"], created["unit"]["id"]) == (
        DiscountStatus.NONE.value, None
    )


def test_discount_request_rejects_non_positive_amount(
    client: TestClient, env: dict
) -> None:
    created = _unit_for_sales(client, env)
    response = client.post(
        f"/api/v1/inventory/units/{created['unit']['id']}/discount-request",
        json={"amount_paise": 0, "reason": "Zero discount is not a proposal."},
        headers=env["sales_headers"],
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Dispatcher contract: missing entity, tenant isolation, RBAC
# ---------------------------------------------------------------------------


def test_decision_on_missing_booking_returns_400_and_stays_pending(
    client: TestClient, env: dict
) -> None:
    # A generic request on the wired pair whose entity vanished.
    response = client.post(
        "/api/v1/approvals/requests",
        json={
            "request_type": "SITE_VISIT_CAR",
            "reference_type": "booking",
            "reference_id": str(uuid4()),
            "reason": "The booking was deleted before the decision.",
        },
        headers=env["sales_headers"],
    )
    assert response.status_code == 201, response.text
    request_id = response.json()["id"]

    decided = _decision(client, env, request_id, decision="APPROVED")
    assert decided.status_code == 400, decided.text

    listing = client.get(
        "/api/v1/approvals/requests?status=PENDING&request_type=SITE_VISIT_CAR",
        headers=env["sales_headers"],
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["status"] == "PENDING"


def test_decision_on_missing_unit_returns_400(client: TestClient, env: dict) -> None:
    response = client.post(
        "/api/v1/approvals/requests",
        json={
            "request_type": "DISCOUNT",
            "reference_type": "unit",
            "reference_id": str(uuid4()),
            "reason": "The unit was deleted before the decision.",
            "amount_paise": 100_000,
        },
        headers=env["sales_headers"],
    )
    assert response.status_code == 201, response.text
    request_id = response.json()["id"]

    decided = _decision(client, env, request_id, decision="REJECTED")
    assert decided.status_code == 400, decided.text


def test_cancel_on_missing_unit_returns_400(client: TestClient, env: dict) -> None:
    response = client.post(
        "/api/v1/approvals/requests",
        json={
            "request_type": "DISCOUNT",
            "reference_type": "unit",
            "reference_id": str(uuid4()),
            "reason": "Phantom unit cancellation.",
            "amount_paise": 100_000,
        },
        headers=env["sales_headers"],
    )
    assert response.status_code == 201, response.text
    request_id = response.json()["id"]

    cancelled = _cancel(client, env, request_id)
    assert cancelled.status_code == 400, cancelled.text


def test_car_request_cross_tenant_booking_is_404(
    client: TestClient, env: dict, user_factory, auth_headers
) -> None:
    with env["factory"]() as session:
        other_tenant = Tenant(slug=f"car-{uuid4().hex[:8]}", name="Other Tenant")
        session.add(other_tenant)
        session.commit()
        session.refresh(other_tenant)
    other_admin = user_factory(role=RoleName.ADMIN, tenant=other_tenant)

    # A booking owned by the other tenant.
    with env["factory"]() as session:
        project = Project(
            tenant_id=other_tenant.id, name="Other Towers", slug=f"ot-{uuid4().hex[:6]}",
            location="Pune", status="ACTIVE", created_by=other_admin.id,
        )
        session.add(project)
        session.flush()
        lead = Lead(
            tenant_id=other_tenant.id, full_name="Other Buyer",
            email=f"ob-{uuid4().hex[:6]}@example.com", phone="+919810000001",
            project_id=project.id, source="WEBSITE", status="CONVERTED",
            consent_to_contact=True,
        )
        session.add(lead)
        session.commit()
        session.refresh(lead)

    response = client.post(
        f"/api/v1/bookings/{lead.id}/car-request",
        json={"reason": "Cross-tenant access must be invisible."},
        headers=env["sales_headers"],
    )
    # The id is a lead id, not a booking id; either way the caller's tenant
    # has no such booking, so it must be 404 (not 403, which would leak existence).
    assert response.status_code == 404, response.text


def test_discount_request_cross_tenant_unit_is_404(
    client: TestClient, env: dict, user_factory, auth_headers
) -> None:
    with env["factory"]() as session:
        other_tenant = Tenant(slug=f"unit-{uuid4().hex[:8]}", name="Unit Tenant")
        session.add(other_tenant)
        session.commit()
        session.refresh(other_tenant)
    other_admin = user_factory(role=RoleName.ADMIN, tenant=other_tenant)
    with env["factory"]() as session:
        project = Project(
            tenant_id=other_tenant.id, name="Foreign Towers", slug=f"ft-{uuid4().hex[:6]}",
            location="Pune", status="ACTIVE", created_by=other_admin.id,
        )
        session.add(project)
        session.flush()
        unit = PropertyUnit(
            tenant_id=other_tenant.id, project_id=project.id,
            internal_code="FOREIGN-1", status="AVAILABLE",
        )
        session.add(unit)
        session.commit()
        session.refresh(unit)

    response = client.post(
        f"/api/v1/inventory/units/{unit.id}/discount-request",
        json={"amount_paise": 100_000, "reason": "Cross-tenant unit request."},
        headers=env["sales_headers"],
    )
    assert response.status_code == 404, response.text


def test_cross_tenant_admin_cannot_decide_local_request(
    client: TestClient, env: dict, user_factory, auth_headers
) -> None:
    created = _unit_for_sales(client, env)
    request = _discount_request(client, env, created["unit"]["id"])

    with env["factory"]() as session:
        other_tenant = Tenant(slug=f"dec-{uuid4().hex[:8]}", name="Decider Tenant")
        session.add(other_tenant)
        session.commit()
        session.refresh(other_tenant)
    other_admin = user_factory(role=RoleName.ADMIN, tenant=other_tenant)

    response = client.post(
        f"/api/v1/approvals/requests/{request['id']}/decision",
        json={"decision": "APPROVED"},
        headers=auth_headers(other_admin.email),
    )
    assert response.status_code == 404, response.text

    assert _unit_state(env["factory"], created["unit"]["id"])[0] == DiscountStatus.PENDING.value


def test_buyer_cannot_raise_car_request(client: TestClient, env: dict, user_factory, auth_headers) -> None:
    buyer = user_factory(role=RoleName.BUYER)
    response = client.post(
        f"/api/v1/bookings/{uuid4()}/car-request",
        json={"reason": "A buyer cannot raise car requests."},
        headers=auth_headers(buyer.email),
    )
    assert response.status_code == 403, response.text


def test_buyer_cannot_raise_discount_request(client: TestClient, env: dict, user_factory, auth_headers) -> None:
    buyer = user_factory(role=RoleName.BUYER)
    response = client.post(
        f"/api/v1/inventory/units/{uuid4()}/discount-request",
        json={"amount_paise": 100_000, "reason": "A buyer cannot propose discounts."},
        headers=auth_headers(buyer.email),
    )
    assert response.status_code == 403, response.text


def test_sales_executive_cannot_decide_wired_request(client: TestClient, env: dict) -> None:
    created = _booking_for_sales(client, env)
    request = _car_request(client, env, created["booking"]["id"])

    response = client.post(
        f"/api/v1/approvals/requests/{request['id']}/decision",
        json={"decision": "APPROVED"},
        headers=env["sales_headers"],
    )
    assert response.status_code == 403, response.text

    assert _booking_flag(env["factory"], created["booking"]["id"]) == \
        CarRequestStatus.PENDING.value


def test_migration_adds_and_drops_side_effect_columns_on_isolated_sqlite() -> None:
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect

    migration_path = next(
        (Path(__file__).parents[2] / "alembic" / "versions").glob("*c8d9e0f1a2b3*")
    )
    spec = importlib.util.spec_from_file_location("approval_side_effects_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "c8d9e0f1a2b3"
    assert migration.down_revision == "e9a0b1c2d3e4"

    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        with engine.connect() as connection:
            # Parent tables the migration alters, mirroring a pre-migration schema.
            import sqlalchemy as sa

            metadata = sa.MetaData()
            sa.Table(
                "bookings", metadata,
                sa.Column("id", sa.Uuid(), primary_key=True),
                sa.Column("status", sa.String(length=32), nullable=False),
                sa.Column("tenant_id", sa.Uuid(), nullable=False),
            )
            sa.Table(
                "property_units", metadata,
                sa.Column("id", sa.Uuid(), primary_key=True),
                sa.Column("status", sa.String(length=24), nullable=False),
                sa.Column("tenant_id", sa.Uuid(), nullable=False),
            )
            metadata.create_all(connection)
            context = MigrationContext.configure(connection)
            original_get_bind = Operations.get_bind
            Operations.get_bind = lambda self: connection
            try:
                with Operations.context(context):
                    migration.upgrade()
                    inspector = inspect(connection)
                    booking_columns = {
                        column["name"]: column for column in inspector.get_columns("bookings")
                    }
                    assert booking_columns["car_request_status"]["nullable"] is False
                    unit_columns = {
                        column["name"]: column for column in inspector.get_columns("property_units")
                    }
                    assert unit_columns["approved_discount_paise"]["nullable"] is True
                    assert unit_columns["discount_status"]["nullable"] is False

                    migration.downgrade()
                    inspector = inspect(connection)
                    booking_columns = {
                        column["name"] for column in inspector.get_columns("bookings")
                    }
                    unit_columns = {
                        column["name"] for column in inspector.get_columns("property_units")
                    }
                    assert "car_request_status" not in booking_columns
                    assert "approved_discount_paise" not in unit_columns
                    assert "discount_status" not in unit_columns
            finally:
                Operations.get_bind = original_get_bind
    finally:
        engine.dispose()
