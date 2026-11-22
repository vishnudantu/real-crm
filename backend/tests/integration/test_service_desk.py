"""Integration tests for the service-desk ticket queue with SLA tracking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from app.modules.service_desk.models import Ticket
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User

BASE = "/api/v1/service-desk/tickets"


@pytest.fixture()
def env(
    client: TestClient,
    override_db: None,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> dict:
    admin = user_factory(role=RoleName.ADMIN)
    sales = user_factory(role=RoleName.SALES_EXECUTIVE, email=f"sales-{uuid4().hex[:6]}@ex.com")
    return {
        "factory": test_session_factory,
        "tenant_id": admin.tenant_id,
        "admin_id": admin.id,
        "admin_headers": auth_headers(admin.email),
        "sales_id": sales.id,
        "sales_headers": auth_headers(sales.email),
    }


def _create(client: TestClient, headers: dict, **overrides) -> dict:
    payload = {"subject": "Leaking pipe", "description": "Water damage in unit A-101"}
    payload.update(overrides)
    response = client.post(BASE, json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _patch_sla_due(factory: sessionmaker[Session], ticket_id: str, due: datetime) -> None:
    with factory() as session:
        session.execute(update(Ticket).where(Ticket.id == UUID(ticket_id)).values(sla_due_at=due))
        session.commit()


class TestCreateAndNumbering:
    def test_sequential_tck_numbers(self, client: TestClient, env) -> None:
        first = _create(client, env["admin_headers"])
        second = _create(client, env["sales_headers"], subject="Second")
        assert first["ticket_number"] == "TCK-000001"
        assert second["ticket_number"] == "TCK-000002"

    def test_numbering_uses_max_not_count(self, client: TestClient, env) -> None:
        first = _create(client, env["admin_headers"])
        # A pre-existing high number must not be reused by a row count.
        with env["factory"]() as session:
            session.add(
                Ticket(
                    tenant_id=env["tenant_id"],
                    ticket_number="TCK-000042",
                    subject="Legacy",
                    description="legacy",
                    category="GENERAL",
                    priority="LOW",
                    status="OPEN",
                    sla_due_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
            session.commit()
        following = _create(client, env["admin_headers"])
        assert following["ticket_number"] == "TCK-000043"

    @pytest.mark.parametrize(
        ("priority", "hours"),
        [("URGENT", 4), ("HIGH", 24), ("MEDIUM", 72), ("LOW", 168)],
    )
    def test_sla_due_at_per_priority(self, client: TestClient, env, priority, hours) -> None:
        before = datetime.now(UTC)
        body = _create(client, env["admin_headers"], priority=priority)
        after = datetime.now(UTC)
        due = datetime.fromisoformat(body["sla_due_at"].replace("Z", "+00:00"))
        if due.tzinfo is None:
            due = due.replace(tzinfo=UTC)
        expected_low = before + timedelta(hours=hours)
        expected_high = after + timedelta(hours=hours)
        assert expected_low <= due <= expected_high
        assert body["priority"] == priority

    def test_default_priority_and_status(self, client: TestClient, env) -> None:
        body = _create(client, env["admin_headers"])
        assert body["priority"] == "MEDIUM"
        assert body["status"] == "OPEN"
        assert body["category"] == "GENERAL"
        assert body["resolved_at"] is None
        assert body["first_response_at"] is None

    def test_validation_422(self, client: TestClient, env) -> None:
        response = client.post(BASE, json={"subject": "   ", "description": "x"}, headers=env["admin_headers"])
        assert response.status_code == 422


class TestComments:
    def test_first_staff_comment_sets_first_response_at(self, client: TestClient, env) -> None:
        ticket = _create(client, env["admin_headers"])
        ticket_id = ticket["id"]
        before = datetime.now(UTC)
        response = client.post(
            f"{BASE}/{ticket_id}/comments",
            json={"body": "I am on it", "is_internal": False},
            headers=env["sales_headers"],
        )
        assert response.status_code == 201, response.text
        comment = response.json()
        assert comment["body"] == "I am on it"
        assert comment["ticket_id"] == ticket_id
        assert comment["author_id"] == str(env["sales_id"])

        detail = client.get(f"{BASE}/{ticket_id}", headers=env["admin_headers"]).json()
        first_response = datetime.fromisoformat(detail["first_response_at"].replace("Z", "+00:00"))
        if first_response.tzinfo is None:
            first_response = first_response.replace(tzinfo=UTC)
        assert first_response >= before
        assert len(detail["comments"]) == 1

        # A second comment does not move the first-response timestamp.
        client.post(
            f"{BASE}/{ticket_id}/comments", json={"body": "Update"}, headers=env["admin_headers"]
        )
        again = client.get(f"{BASE}/{ticket_id}", headers=env["admin_headers"]).json()
        assert again["first_response_at"] == detail["first_response_at"]
        assert len(again["comments"]) == 2

    def test_internal_flag_persisted(self, client: TestClient, env) -> None:
        ticket = _create(client, env["admin_headers"])
        client.post(
            f"{BASE}/{ticket['id']}/comments",
            json={"body": "Internal note", "is_internal": True},
            headers=env["admin_headers"],
        )
        detail = client.get(f"{BASE}/{ticket['id']}", headers=env["admin_headers"]).json()
        assert detail["comments"][0]["is_internal"] is True

    def test_empty_body_422(self, client: TestClient, env) -> None:
        ticket = _create(client, env["admin_headers"])
        response = client.post(
            f"{BASE}/{ticket['id']}/comments", json={"body": "   "}, headers=env["admin_headers"]
        )
        assert response.status_code == 422

    def test_comment_on_unknown_ticket_404(self, client: TestClient, env) -> None:
        response = client.post(
            f"{BASE}/{uuid4()}/comments", json={"body": "ghost"}, headers=env["admin_headers"]
        )
        assert response.status_code == 404


class TestAssignment:
    def test_assign_to_staff(self, client: TestClient, env) -> None:
        ticket = _create(client, env["admin_headers"])
        response = client.post(
            f"{BASE}/{ticket['id']}/assign",
            json={"assigned_to_id": str(env["sales_id"])},
            headers=env["admin_headers"],
        )
        assert response.status_code == 200, response.text
        assert response.json()["assigned_to_id"] == str(env["sales_id"])

    def test_assign_to_buyer_400(self, client: TestClient, env, user_factory, auth_headers) -> None:
        buyer = user_factory(role=RoleName.BUYER, email=f"buyer-{uuid4().hex[:6]}@ex.com")
        ticket = _create(client, env["admin_headers"])
        response = client.post(
            f"{BASE}/{ticket['id']}/assign",
            json={"assigned_to_id": str(buyer.id)},
            headers=env["admin_headers"],
        )
        assert response.status_code == 400


class TestStatusTransitions:
    def test_resolve_sets_resolved_at_and_note(self, client: TestClient, env) -> None:
        ticket = _create(client, env["admin_headers"])
        response = client.patch(
            f"{BASE}/{ticket['id']}/status",
            json={"status": "RESOLVED", "resolution_note": "Pipe replaced"},
            headers=env["admin_headers"],
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "RESOLVED"
        assert body["resolved_at"] is not None
        assert body["resolution_note"] == "Pipe replaced"

        close = client.patch(
            f"{BASE}/{ticket['id']}/status", json={"status": "CLOSED"}, headers=env["admin_headers"]
        )
        assert close.status_code == 200 and close.json()["status"] == "CLOSED"

    def test_open_to_in_progress(self, client: TestClient, env) -> None:
        ticket = _create(client, env["admin_headers"])
        response = client.patch(
            f"{BASE}/{ticket['id']}/status", json={"status": "IN_PROGRESS"}, headers=env["admin_headers"]
        )
        assert response.status_code == 200
        assert response.json()["resolved_at"] is None

    def test_illegal_open_to_in_progress_then_open_again_409(self, client: TestClient, env) -> None:
        ticket = _create(client, env["admin_headers"])
        client.patch(
            f"{BASE}/{ticket['id']}/status", json={"status": "IN_PROGRESS"}, headers=env["admin_headers"]
        )
        # IN_PROGRESS -> OPEN is not allowed.
        response = client.patch(
            f"{BASE}/{ticket['id']}/status", json={"status": "OPEN"}, headers=env["admin_headers"]
        )
        assert response.status_code == 409

    def test_resolved_cannot_reopen_409(self, client: TestClient, env) -> None:
        ticket = _create(client, env["admin_headers"])
        client.patch(
            f"{BASE}/{ticket['id']}/status", json={"status": "RESOLVED"}, headers=env["admin_headers"]
        )
        response = client.patch(
            f"{BASE}/{ticket['id']}/status", json={"status": "IN_PROGRESS"}, headers=env["admin_headers"]
        )
        assert response.status_code == 409

    def test_waiting_on_customer_round_trip(self, client: TestClient, env) -> None:
        ticket = _create(client, env["admin_headers"])
        response = client.patch(
            f"{BASE}/{ticket['id']}/status",
            json={"status": "WAITING_ON_CUSTOMER"},
            headers=env["admin_headers"],
        )
        assert response.status_code == 200
        resume = client.patch(
            f"{BASE}/{ticket['id']}/status", json={"status": "IN_PROGRESS"}, headers=env["admin_headers"]
        )
        assert resume.status_code == 200

    def test_in_progress_cannot_close_directly_409(self, client: TestClient, env) -> None:
        ticket = _create(client, env["admin_headers"])
        client.patch(
            f"{BASE}/{ticket['id']}/status", json={"status": "IN_PROGRESS"}, headers=env["admin_headers"]
        )
        response = client.patch(
            f"{BASE}/{ticket['id']}/status", json={"status": "CLOSED"}, headers=env["admin_headers"]
        )
        assert response.status_code == 409


class TestListAndBreachQueue:
    def test_breach_only_returns_overdue_open_tickets(self, client: TestClient, env) -> None:
        breached = _create(client, env["admin_headers"], subject="Breached")
        _create(client, env["admin_headers"], subject="Fresh")
        # Move the breached ticket's SLA deadline into the past.
        _patch_sla_due(env["factory"], breached["id"], datetime.now(UTC) - timedelta(hours=1))

        response = client.get(f"{BASE}?breach_only=true", headers=env["admin_headers"])
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["subject"] == "Breached"

    def test_resolved_past_sla_is_not_a_breach(self, client: TestClient, env) -> None:
        ticket = _create(client, env["admin_headers"], subject="Resolved late")
        client.patch(
            f"{BASE}/{ticket['id']}/status", json={"status": "RESOLVED"}, headers=env["admin_headers"]
        )
        _patch_sla_due(env["factory"], ticket["id"], datetime.now(UTC) - timedelta(hours=2))
        response = client.get(f"{BASE}?breach_only=true", headers=env["admin_headers"])
        assert response.json()["total"] == 0

    def test_filters_status_priority_assigned(self, client: TestClient, env) -> None:
        ticket = _create(client, env["admin_headers"], priority="URGENT")
        client.post(
            f"{BASE}/{ticket['id']}/assign",
            json={"assigned_to_id": str(env["sales_id"])},
            headers=env["admin_headers"],
        )
        client.patch(
            f"{BASE}/{ticket['id']}/status", json={"status": "IN_PROGRESS"}, headers=env["admin_headers"]
        )
        _create(client, env["admin_headers"], priority="LOW", subject="Other")

        by_status = client.get(f"{BASE}?status=IN_PROGRESS", headers=env["admin_headers"]).json()
        assert by_status["total"] == 1 and by_status["items"][0]["id"] == ticket["id"]

        by_priority = client.get(f"{BASE}?priority=URGENT", headers=env["admin_headers"]).json()
        assert by_priority["total"] == 1

        by_assigned = client.get(
            f"{BASE}?assigned_to_id={env['sales_id']}", headers=env["admin_headers"]
        ).json()
        assert by_assigned["total"] == 1

    def test_pagination_metadata(self, client: TestClient, env) -> None:
        for _ in range(3):
            _create(client, env["admin_headers"])
        body = client.get(f"{BASE}?limit=2&offset=0", headers=env["admin_headers"]).json()
        assert body["total"] == 3 and body["limit"] == 2 and body["offset"] == 0
        assert len(body["items"]) == 2


class TestTenantIsolationAndAccess:
    def test_cross_tenant_detail_404(self, client: TestClient, env, user_factory, auth_headers) -> None:
        ticket = _create(client, env["admin_headers"])
        other_tenant = Tenant(slug=f"other-{uuid4().hex[:8]}", name="Other")
        with env["factory"]() as session:
            session.add(other_tenant)
            session.flush()
            other_admin = user_factory(
                role=RoleName.ADMIN,
                tenant=other_tenant,
                email=f"other-admin-{uuid4().hex[:6]}@ex.com",
            )
            other_headers = auth_headers(other_admin.email)
        response = client.get(f"{BASE}/{ticket['id']}", headers=other_headers)
        assert response.status_code == 404

    def test_cross_tenant_mutation_404(self, client: TestClient, env, user_factory, auth_headers) -> None:
        ticket = _create(client, env["admin_headers"])
        other_tenant = Tenant(slug=f"other-{uuid4().hex[:8]}", name="Other")
        with env["factory"]() as session:
            session.add(other_tenant)
            session.flush()
            other_admin = user_factory(
                role=RoleName.ADMIN,
                tenant=other_tenant,
                email=f"other-admin2-{uuid4().hex[:6]}@ex.com",
            )
            other_headers = auth_headers(other_admin.email)
        comment = client.post(
            f"{BASE}/{ticket['id']}/comments", json={"body": "steal"}, headers=other_headers
        )
        assert comment.status_code == 404
        status = client.patch(
            f"{BASE}/{ticket['id']}/status", json={"status": "CLOSED"}, headers=other_headers
        )
        assert status.status_code == 404

    def test_cross_tenant_list_is_scoped(self, client: TestClient, env, user_factory, auth_headers) -> None:
        _create(client, env["admin_headers"])
        other_tenant = Tenant(slug=f"other-{uuid4().hex[:8]}", name="Other")
        with env["factory"]() as session:
            session.add(other_tenant)
            session.flush()
            other_admin = user_factory(
                role=RoleName.ADMIN,
                tenant=other_tenant,
                email=f"other-admin3-{uuid4().hex[:6]}@ex.com",
            )
            other_headers = auth_headers(other_admin.email)
        listing = client.get(BASE, headers=other_headers).json()
        assert listing["total"] == 0

    def test_buyer_forbidden(self, client: TestClient, env, user_factory, auth_headers) -> None:
        buyer = user_factory(role=RoleName.BUYER, email=f"buyer-{uuid4().hex[:6]}@ex.com")
        buyer_headers = auth_headers(buyer.email)
        response = client.post(
            BASE,
            json={"subject": "x", "description": "y"},
            headers=buyer_headers,
        )
        assert response.status_code == 403
        assert client.get(BASE, headers=buyer_headers).status_code == 403

    def test_sales_executive_full_access(self, client: TestClient, env) -> None:
        ticket = _create(client, env["sales_headers"], subject="From sales")
        assert ticket["created_by_id"] == str(env["sales_id"])
        assert client.get(BASE, headers=env["sales_headers"]).json()["total"] == 1


class TestContactBookingLinks:
    def test_contact_link_stored(self, client: TestClient, env) -> None:
        from app.modules.customers.models import Contact

        with env["factory"]() as session:
            contact = Contact(
                tenant_id=env["tenant_id"],
                canonical_key=f"uuid:{uuid4()}",
                display_name="Ticket Contact",
            )
            session.add(contact)
            session.commit()
            contact_id = str(contact.id)
        body = _create(client, env["admin_headers"], contact_id=contact_id)
        assert body["contact_id"] == contact_id

    def test_foreign_contact_link_400(self, client: TestClient, env) -> None:
        from app.modules.customers.models import Contact

        other_tenant = Tenant(slug=f"other-{uuid4().hex[:8]}", name="Other")
        with env["factory"]() as session:
            session.add(other_tenant)
            session.flush()
            contact = Contact(
                tenant_id=other_tenant.id,
                canonical_key=f"uuid:{uuid4()}",
                display_name="Other Contact",
            )
            session.add(contact)
            session.commit()
            contact_id = str(contact.id)
        response = client.post(
            BASE,
            json={"subject": "x", "description": "y", "contact_id": contact_id},
            headers=env["admin_headers"],
        )
        assert response.status_code == 400
