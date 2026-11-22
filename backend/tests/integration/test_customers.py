"""Integration route tests for /customers and /opportunities (PF-008/009)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.bookings.models import Booking, VisitSlot
from app.modules.conversations.models import Conversation, Message
from app.modules.customers import service
from app.modules.customers.models import Contact, ContactMethod, ContactMethodKind
from app.modules.leads.models import Lead, LeadSource
from app.modules.omnichannel.models import (
    CallRecord,
    ChannelConversation,
    ChannelMessage,
)
from app.modules.postsales.models import (
    Installment,
    PaymentPlan,
    Receipt,
    SaleBooking,
)
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from tests.support import TEST_PASSWORD


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
    with test_session_factory() as s:
        project = Project(
            tenant_id=admin.tenant_id,
            name="P",
            slug=f"p-{uuid4().hex[:8]}",
            location="X",
            status=ProjectStatus.ACTIVE.value,
            created_by=admin.id,
        )
        s.add(project)
        s.commit()
        return {
            "factory": test_session_factory,
            "tenant_id": admin.tenant_id,
            "admin_id": admin.id,
            "admin_email": admin.email,
            "headers": headers,
            "project_id": project.id,
        }


def _make_contact_with_full_graph(env: dict) -> tuple[str, str]:
    """Create a contact + one row per timeline source; return (contact_id, lead_id)."""
    with env["factory"]() as s:
        admin = s.get(User, env["admin_id"])
        contact, _, _ = service.resolve_contact(
            s,
            tenant_id=env["tenant_id"],
            email="full@ex.com",
            phone="+919812345678",
            display_name="Full Graph",
        )
        s.flush()
        lead = Lead(
            tenant_id=env["tenant_id"],
            full_name="Full Graph",
            email="full@ex.com",
            phone="+919812345678",
            project_id=env["project_id"],
            source=LeadSource.WEBSITE.value,
            status="CONVERTED",
            consent_to_contact=True,
        )
        s.add(lead)
        s.flush()
        service.open_opportunity(
            s,
            actor=admin,
            contact_id=contact.id,
            project_id=env["project_id"],
            from_lead_id=lead.id,
        )
        buyer = User(
            tenant_id=env["tenant_id"],
            full_name="B",
            email=f"b-{uuid4().hex[:6]}@ex.com",
            password_hash="x",
            role_id=admin.role_id,
        )
        s.add(buyer)
        s.flush()
        conv = Conversation(
            tenant_id=env["tenant_id"],
            lead_id=lead.id,
            project_id=env["project_id"],
            buyer_id=buyer.id,
        )
        s.add(conv)
        s.flush()
        s.add(
            Message(
                tenant_id=env["tenant_id"],
                conversation_id=conv.id,
                sender_type="BUYER",
                content="hello",
            )
        )
        chan = ChannelConversation(
            tenant_id=env["tenant_id"],
            lead_id=lead.id,
            channel="WHATSAPP",
            external_thread_id=f"t-{uuid4().hex[:6]}",
        )
        s.add(chan)
        s.flush()
        s.add(
            ChannelMessage(
                tenant_id=env["tenant_id"],
                conversation_id=chan.id,
                channel="WHATSAPP",
                direction="INBOUND",
                content="hi",
            )
        )
        slot = VisitSlot(
            tenant_id=env["tenant_id"],
            project_id=env["project_id"],
            start_time=__import__("datetime").datetime(2030, 1, 1, 10),
            end_time=__import__("datetime").datetime(2030, 1, 1, 11),
        )
        s.add(slot)
        s.flush()
        s.add(
            Booking(
                tenant_id=env["tenant_id"],
                slot_id=slot.id,
                lead_id=lead.id,
                project_id=env["project_id"],
                buyer_id=buyer.id,
            )
        )
        s.add(
            CallRecord(
                tenant_id=env["tenant_id"],
                lead_id=lead.id,
                agent_id=admin.id,
                direction="OUTBOUND",
                status="COMPLETED",
                provider="simulated",
                room_name=f"r-{uuid4().hex[:6]}",
            )
        )
        sale = SaleBooking(
            tenant_id=env["tenant_id"],
            lead_id=lead.id,
            project_id=env["project_id"],
            unit_number="A-101",
            consideration_paise=100000,
        )
        s.add(sale)
        s.flush()
        plan = PaymentPlan(
            tenant_id=env["tenant_id"],
            sale_booking_id=sale.id,
            name="Plan",
            plan_type="TIME_LINKED",
        )
        s.add(plan)
        s.flush()
        inst = Installment(
            tenant_id=env["tenant_id"],
            plan_id=plan.id,
            sequence_no=1,
            milestone="M1",
            amount_paise=50000,
            due_on=__import__("datetime").date(2030, 1, 1),
        )
        s.add(inst)
        s.flush()
        s.add(
            Receipt(
                tenant_id=env["tenant_id"],
                installment_id=inst.id,
                receipt_number=f"R-{uuid4().hex[:6]}",
                amount_paise=50000,
                channel="UPI",
            )
        )
        s.commit()
        return str(contact.id), str(lead.id)


class TestSearch:
    def test_preview_would_create(self, client: TestClient, env) -> None:
        r = client.post(
            "/api/v1/customers/search",
            json={"email": "nobody@ex.com"},
            headers=env["headers"],
        )
        assert r.status_code == 200
        body = r.json()
        assert body["exists"] is False and body["would_create"] is True

    def test_preview_existing(self, client: TestClient, env) -> None:
        with env["factory"]() as s:
            service.resolve_contact(s, tenant_id=env["tenant_id"], email="have@ex.com")
            s.commit()
        r = client.post(
            "/api/v1/customers/search",
            json={"email": "HAVE@ex.com"},
            headers=env["headers"],
        )
        assert r.json()["exists"] is True


class TestCustomer360:
    def test_aggregation_shape_one_row_per_source(self, client: TestClient, env) -> None:
        contact_id, _ = _make_contact_with_full_graph(env)
        r = client.get(f"/api/v1/customers/{contact_id}", headers=env["headers"])
        assert r.status_code == 200, r.text
        body = r.json()
        types = {item["type"] for item in body["timeline"]}
        assert {
            "lead",
            "conversation",
            "message",
            "channel_conversation",
            "channel_message",
            "booking",
            "call",
            "sale_booking",
            "receipt",
        } <= types
        assert set(body["freshness"]) == {
            "leads",
            "conversations",
            "channels",
            "bookings",
            "calls",
            "sales",
        }
        assert body["contact"]["id"] == contact_id


class TestTenantIsolation:
    def test_cross_tenant_read_404(self, client: TestClient, env, user_factory, auth_headers) -> None:
        other_tenant = Tenant(slug=f"o-{uuid4().hex[:8]}", name="O")
        with env["factory"]() as s:
            s.add(other_tenant)
            s.flush()
            contact = Contact(
                tenant_id=other_tenant.id,
                canonical_key=f"uuid:{uuid4()}",
                display_name="Other",
            )
            s.add(contact)
            s.commit()
            other_contact_id = str(contact.id)
        # admin in default tenant tries to read other tenant's contact
        r = client.get(f"/api/v1/customers/{other_contact_id}", headers=env["headers"])
        assert r.status_code == 404


class TestBuyerAccess:
    def test_buyer_cannot_read_other_contact(self, client: TestClient, env, user_factory, auth_headers) -> None:
        contact_id, _ = _make_contact_with_full_graph(env)
        buyer = user_factory(role=RoleName.BUYER, email="stranger@ex.com")
        headers = auth_headers(buyer.email)
        r = client.get(f"/api/v1/customers/{contact_id}", headers=headers)
        assert r.status_code == 403

    def test_buyer_can_read_own_contact(self, client: TestClient, env, user_factory, auth_headers) -> None:
        buyer = user_factory(role=RoleName.BUYER, email="me@ex.com")
        with env["factory"]() as s:
            contact = Contact(
                tenant_id=env["tenant_id"],
                canonical_key=f"uuid:{uuid4()}",
                display_name="Me",
            )
            s.add(contact)
            s.flush()
            s.add(
                ContactMethod(
                    tenant_id=env["tenant_id"],
                    contact_id=contact.id,
                    kind=ContactMethodKind.EMAIL.value,
                    value="me@ex.com",
                    normalized_value="me@ex.com",
                    is_primary=True,
                )
            )
            s.commit()
            cid = str(contact.id)
        headers = auth_headers(buyer.email)
        r = client.get(f"/api/v1/customers/{cid}", headers=headers)
        assert r.status_code == 200


class TestStageTransitionRoute:
    def test_illegal_transition_returns_409(self, client: TestClient, env) -> None:
        contact_id, _ = _make_contact_with_full_graph(env)
        with env["factory"]() as s:
            admin = s.get(User, env["admin_id"])
            opp = service.open_opportunity(
                s, actor=admin, contact_id=UUID(contact_id), project_id=env["project_id"]
            )
            opp_id = str(opp.id)
        r = client.patch(
            f"/api/v1/opportunities/{opp_id}",
            json={"stage": "WON"},
            headers=env["headers"],
        )
        assert r.status_code == 409
