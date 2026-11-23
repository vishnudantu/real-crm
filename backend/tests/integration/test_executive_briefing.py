"""Morning briefing determinism and admin-gated executive routes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.security import hash_password
import app.modules.executive.briefing as briefing_service
from app.modules.postsales.models import Installment, InstallmentStatus
from app.modules.service_desk.models import Ticket, TicketPriority, TicketStatus
from app.modules.tenancy.models import Tenant
from app.modules.users import repository as users_repo
from app.modules.users.models import RoleName, User
from tests.integration.test_executive_cockpit import (
    _fixture,
    _lead,
    _receipt,
    _sale_booking,
)
from tests.support import TEST_PASSWORD


@pytest.fixture()
def cockpit_client(client: TestClient, override_db: None, seeded_roles: None) -> TestClient:
    return client


def _login_headers(client: TestClient, email: str) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _seed_users(
    test_session_factory: sessionmaker[Session],
    *,
    users: list[tuple[str, str, RoleName]],
) -> None:
    with test_session_factory() as session:
        tenant = Tenant(slug=f"r-{uuid4().hex[:8]}", name="Route Co")
        session.add(tenant)
        session.flush()
        for full_name, email, role_name in users:
            role = users_repo.get_role_by_name(session, role_name)
            assert role is not None, f"missing seeded role {role_name}"
            session.add(
                User(
                    tenant_id=tenant.id, full_name=full_name, email=email,
                    password_hash=hash_password(TEST_PASSWORD),
                    role_id=role.id, is_active=True,
                )
            )
        session.commit()


def test_briefing_counts_are_exact_and_lines_stay_stable(
    test_session_factory: sessionmaker[Session],
) -> None:
    yesterday = (datetime.now(UTC) - timedelta(days=1)).date()
    at_8 = datetime(yesterday.year, yesterday.month, yesterday.day, 8, tzinfo=UTC)

    with test_session_factory() as session:
        tenant, admin, project = _fixture(session)
        lead = _lead(session, tenant, project, created_at=at_8)
        # Book the visit on the briefing day itself so created_at lands in the
        # day window (the shared helper back-dates it by one day by default).
        from app.modules.bookings.models import Booking, BookingStatus, VisitSlot

        slot = VisitSlot(
            tenant_id=tenant.id, project_id=project.id,
            start_time=at_8.replace(hour=15), end_time=at_8.replace(hour=16),
        )
        session.add(slot)
        session.flush()
        session.add(
            Booking(
                tenant_id=tenant.id, slot_id=slot.id, lead_id=lead.id,
                project_id=project.id, buyer_id=admin.id,
                status=BookingStatus.COMPLETED.value, created_at=at_8,
            )
        )
        session.flush()
        _sale_booking(
            session, tenant, project, lead, unit_number="B-1",
            consideration_paise=75_00_00_00, booked_on=yesterday,
            installments=[("Booking", 10_00_00_00, yesterday, InstallmentStatus.DUE)],
        )
        inst = session.scalars(select(Installment).where(Installment.milestone == "Booking")).first()
        _receipt(session, tenant, inst, amount_paise=10_00_00_00, paid_at=at_8.replace(hour=18))
        session.add(
            Ticket(
                tenant_id=tenant.id, ticket_number=f"TCK-{uuid4().hex[:6]}",
                subject="SLA breach", description="x",
                status=TicketStatus.OPEN.value, priority=TicketPriority.MEDIUM.value,
                sla_due_at=datetime.now(UTC) - timedelta(hours=1),
                created_at=at_8,
            )
        )
        session.commit()

        first = briefing_service.briefing(session, tenant_id=tenant.id, briefing_date=yesterday)
        second = briefing_service.briefing(session, tenant_id=tenant.id, briefing_date=yesterday)

        assert first["briefing_date"] == yesterday
        counts = first["counts"]
        assert counts["leads"] == 1
        assert counts["visits_completed"] == 1
        assert counts["visit_bookings_created"] == 1
        assert counts["sale_bookings"] == 1
        assert counts["sale_booking_value_paise"] == 75_00_00_00
        assert counts["receipts"] == 1
        assert counts["receipts_paise"] == 10_00_00_00
        assert counts["tickets_created"] == 1
        assert counts["approvals_decided"] == 0

        open_items = first["open_items"]
        assert open_items["tickets_breaching_sla"] == 1
        assert open_items["overdue_installments"] == 1
        assert open_items["active_sale_bookings"] == 1
        assert open_items["unassigned_active_leads"] == 1

        assert first["lines"] == second["lines"]
        assert any("₹1.00 L" in line for line in first["lines"])

        empty = briefing_service.briefing(session, tenant_id=tenant.id, briefing_date=yesterday - timedelta(days=1))
        assert empty["counts"]["leads"] == 0
        assert any("no payments received" in line for line in empty["lines"])


def test_cockpit_route_requires_admin(cockpit_client, test_session_factory) -> None:
    _seed_users(
        test_session_factory,
        users=[
            ("Exec Gate", "exec-gate@x.example", RoleName.SALES_EXECUTIVE),
            ("Admin Gate", "admin-gate@x.example", RoleName.ADMIN),
        ],
    )

    resp = cockpit_client.get("/api/v1/executive/cockpit")
    assert resp.status_code == 401

    resp = cockpit_client.get(
        "/api/v1/executive/cockpit",
        headers=_login_headers(cockpit_client, "exec-gate@x.example"),
    )
    assert resp.status_code == 403

    resp = cockpit_client.get(
        "/api/v1/executive/cockpit",
        headers=_login_headers(cockpit_client, "admin-gate@x.example"),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["sales_velocity"]) == 12
    assert {"inventory", "approvals", "overdue_installments", "ticket_sla", "project_ranking"} <= set(body)


def test_briefing_route_deterministic_and_validates_date(
    cockpit_client, test_session_factory
) -> None:
    _seed_users(
        test_session_factory,
        users=[("Brief Admin", "brief-admin@x.example", RoleName.ADMIN)],
    )
    headers = _login_headers(cockpit_client, "brief-admin@x.example")

    fixed = "2026-11-01"
    first = cockpit_client.get(f"/api/v1/executive/briefing?date={fixed}", headers=headers)
    second = cockpit_client.get(f"/api/v1/executive/briefing?date={fixed}", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["briefing_date"] == fixed
    assert first.json()["lines"] == second.json()["lines"]

    bad = cockpit_client.get("/api/v1/executive/briefing?date=not-a-date", headers=headers)
    assert bad.status_code == 422

    anon = cockpit_client.get("/api/v1/executive/briefing")
    assert anon.status_code == 401
