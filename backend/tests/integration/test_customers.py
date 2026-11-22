"""Integration route tests for /customers and /opportunities (PF-008/009)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.bookings.models import Booking, VisitSlot
from app.modules.conversations.models import Conversation, Message
from app.modules.customers import service
from app.modules.customers.models import (
    Contact,
    ContactMerge,
    ContactMethod,
    ContactMethodKind,
    ContactStatus,
)
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


class TestContactCreate:
    """POST /customers/contacts — console create + idempotency semantics."""

    def test_create_returns_201_with_provenance_and_profile_fields(
        self, client: TestClient, env
    ) -> None:
        r = client.post(
            "/api/v1/customers/contacts",
            json={
                "display_name": "Console Person",
                "email": "  Console@Ex.com  ",
                "phone": "+91 96115 02119",
                "primary_language": "kn",
                "notes": "walk-in",
            },
            headers=env["headers"],
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["created"] is True
        contact = body["contact"]
        assert contact["display_name"] == "Console Person"
        assert contact["primary_language"] == "kn"
        assert contact["notes"] == "walk-in"
        # uuid canonical key stands at create (methods are UNVERIFIED)
        assert contact["canonical_key"].startswith("uuid:")
        method = body["method"]
        # email is the primary method (first candidate in resolve order)
        assert method["kind"] == "EMAIL"
        assert method["normalized_value"] == "console@ex.com"
        assert method["is_primary"] is True
        prov = method["provenance"]
        assert prov["source"] == "admin_manual"
        assert prov["method"] == "console"
        assert prov["actor_user_id"] == str(env["admin_id"])
        assert "captured_at" in prov
        # secondary phone method exists on the contact detail
        kinds = {m["kind"] for m in contact["methods"]}
        assert kinds == {"EMAIL", "PHONE"}

    def test_identical_resubmission_is_idempotent_200_not_409(
        self, client: TestClient, env
    ) -> None:
        payload = {"display_name": "Repeat", "email": "repeat@ex.com"}
        r1 = client.post(
            "/api/v1/customers/contacts", json=payload, headers=env["headers"]
        )
        assert r1.status_code == 201
        # same submission, differently-cased email + whitespace
        r2 = client.post(
            "/api/v1/customers/contacts",
            json={"display_name": "Repeat", "email": " REPEAT@ex.com "},
            headers=env["headers"],
        )
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2["created"] is False
        assert body2["contact"]["id"] == r1.json()["contact"]["id"]
        assert body2["method"]["id"] == r1.json()["method"]["id"]
        # existing contact keeps its original profile fields
        assert body2["contact"]["display_name"] == "Repeat"

    def test_phone_match_resolves_to_email_contact(self, client, env) -> None:
        r1 = client.post(
            "/api/v1/customers/contacts",
            json={"display_name": "Both", "email": "both@ex.com", "phone": "+919876543210"},
            headers=env["headers"],
        )
        assert r1.status_code == 201
        r2 = client.post(
            "/api/v1/customers/contacts",
            json={"display_name": "Both", "phone": "+91-9876-543-210"},
            headers=env["headers"],
        )
        assert r2.status_code == 200
        assert r2.json()["contact"]["id"] == r1.json()["contact"]["id"]
        # matched by the PHONE method
        assert r2.json()["method"]["kind"] == "PHONE"

    @pytest.mark.parametrize(
        "payload",
        [
            {"display_name": "No Identity"},
            {"display_name": "Bad Email", "email": "not-an-email"},
            {"display_name": "Short"},
            {"display_name": "x" * 256, "email": "a@ex.com"},
        ],
    )
    def test_validation_422(self, client: TestClient, env, payload: dict) -> None:
        r = client.post(
            "/api/v1/customers/contacts", json=payload, headers=env["headers"]
        )
        assert r.status_code == 422

    def test_create_requires_manager_role(self, client, env, user_factory, auth_headers) -> None:
        buyer = user_factory(role=RoleName.BUYER, email=f"b-{uuid4().hex[:8]}@ex.com")
        headers = auth_headers(buyer.email)
        r = client.post(
            "/api/v1/customers/contacts",
            json={"display_name": "Denied", "email": "denied@ex.com"},
            headers=headers,
        )
        assert r.status_code == 403


class TestContactPatch:
    """PATCH /customers/contacts/{id} — editable fields only."""

    def _create(self, client: TestClient, env) -> str:
        r = client.post(
            "/api/v1/customers/contacts",
            json={"display_name": "Patchable", "email": "patch@ex.com"},
            headers=env["headers"],
        )
        assert r.status_code == 201
        return r.json()["contact"]["id"]

    def test_allowed_fields_update(self, client: TestClient, env) -> None:
        contact_id = self._create(client, env)
        r = client.patch(
            f"/api/v1/customers/contacts/{contact_id}",
            json={"display_name": "Renamed", "primary_language": "ta", "notes": "vip"},
            headers=env["headers"],
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["display_name"] == "Renamed"
        assert body["primary_language"] == "ta"
        assert body["notes"] == "vip"

    def test_canonical_key_untouched_by_patch(self, client: TestClient, env) -> None:
        contact_id = self._create(client, env)
        before = client.get(
            f"/api/v1/customers/{contact_id}", headers=env["headers"]
        ).json()["contact"]["canonical_key"]
        client.patch(
            f"/api/v1/customers/contacts/{contact_id}",
            json={"notes": "changed"},
            headers=env["headers"],
        )
        after = client.get(
            f"/api/v1/customers/{contact_id}", headers=env["headers"]
        ).json()["contact"]["canonical_key"]
        assert after == before

    @pytest.mark.parametrize("body", [{"status": "ANONYMIZED"}, {"merged_into_id": str(uuid4())}])
    def test_disallowed_fields_rejected_422(
        self, client: TestClient, env, body: dict
    ) -> None:
        contact_id = self._create(client, env)
        r = client.patch(
            f"/api/v1/customers/contacts/{contact_id}",
            json=body,
            headers=env["headers"],
        )
        assert r.status_code == 422

    def test_empty_body_400(self, client: TestClient, env) -> None:
        contact_id = self._create(client, env)
        r = client.patch(
            f"/api/v1/customers/contacts/{contact_id}",
            json={},
            headers=env["headers"],
        )
        assert r.status_code == 400

    def test_invalid_values_422(self, client: TestClient, env) -> None:
        contact_id = self._create(client, env)
        r = client.patch(
            f"/api/v1/customers/contacts/{contact_id}",
            json={"display_name": "x"},
            headers=env["headers"],
        )
        assert r.status_code == 422

    def test_cross_tenant_404(self, client: TestClient, env) -> None:
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
        r = client.patch(
            f"/api/v1/customers/contacts/{other_contact_id}",
            json={"notes": "stolen"},
            headers=env["headers"],
        )
        assert r.status_code == 404

    def test_unknown_contact_404(self, client: TestClient, env) -> None:
        r = client.patch(
            f"/api/v1/customers/contacts/{uuid4()}",
            json={"notes": "ghost"},
            headers=env["headers"],
        )
        assert r.status_code == 404

    def test_merged_contact_not_editable_400(
        self, client: TestClient, env
    ) -> None:
        survivor = self._create(client, env)
        r2 = client.post(
            "/api/v1/customers/contacts",
            json={"display_name": "Loser", "email": "loser@ex.com"},
            headers=env["headers"],
        )
        loser = r2.json()["contact"]["id"]
        rm = client.post(
            f"/api/v1/customers/{survivor}/merge",
            json={"merged_id": loser, "reason": "dup"},
            headers=env["headers"],
        )
        assert rm.status_code == 201
        rp = client.patch(
            f"/api/v1/customers/contacts/{loser}",
            json={"notes": "late"},
            headers=env["headers"],
        )
        assert rp.status_code == 400

    def test_patch_requires_manager_role(
        self, client: TestClient, env, user_factory, auth_headers
    ) -> None:
        contact_id = self._create(client, env)
        buyer = user_factory(role=RoleName.BUYER, email=f"pb-{uuid4().hex[:8]}@ex.com")
        headers = auth_headers(buyer.email)
        r = client.patch(
            f"/api/v1/customers/contacts/{contact_id}",
            json={"notes": "nope"},
            headers=headers,
        )
        assert r.status_code == 403

    def test_sales_executive_can_create_and_patch(self, client, env, user_factory, auth_headers) -> None:
        sales = user_factory(
            role=RoleName.SALES_EXECUTIVE, email=f"s-{uuid4().hex[:8]}@ex.com"
        )
        headers = auth_headers(sales.email)
        r = client.post(
            "/api/v1/customers/contacts",
            json={"display_name": "Sales Create", "phone": "+919000000001"},
            headers=headers,
        )
        assert r.status_code == 201
        contact_id = r.json()["contact"]["id"]
        rp = client.patch(
            f"/api/v1/customers/contacts/{contact_id}",
            json={"notes": "by sales"},
            headers=headers,
        )
        assert rp.status_code == 200
        assert rp.json()["notes"] == "by sales"


class TestMergeHistory:
    """GET /customers/merges — pagination + revert flow via history."""

    def _merge_two(self, client: TestClient, env, tag: str) -> tuple[str, str]:
        r1 = client.post(
            "/api/v1/customers/contacts",
            json={"display_name": f"S {tag}", "email": f"s-{tag}@ex.com"},
            headers=env["headers"],
        )
        r2 = client.post(
            "/api/v1/customers/contacts",
            json={"display_name": f"M {tag}", "email": f"m-{tag}@ex.com"},
            headers=env["headers"],
        )
        survivor = r1.json()["contact"]["id"]
        merged = r2.json()["contact"]["id"]
        rm = client.post(
            f"/api/v1/customers/{survivor}/merge",
            json={"merged_id": merged, "reason": f"dupe-{tag}"},
            headers=env["headers"],
        )
        assert rm.status_code == 201, rm.text
        return survivor, merged

    def _order_merges(self, env, newer_reason: str) -> None:
        """Pin created_at so newest-first ordering is deterministic (SQLite
        CURRENT_TIMESTAMP has second precision)."""
        from datetime import UTC, datetime

        from sqlalchemy import update

        now = datetime.now(UTC)
        with env["factory"]() as s:
            s.execute(
                update(ContactMerge)
                .where(ContactMerge.reason == newer_reason)
                .values(created_at=now)
            )
            s.execute(
                update(ContactMerge)
                .where(ContactMerge.reason != newer_reason)
                .values(created_at=datetime(2026, 1, 1, tzinfo=UTC))
            )
            s.commit()

    def test_newest_first_and_contract_fields(self, client: TestClient, env) -> None:
        survivor, merged = self._merge_two(client, env, "hist")
        self._merge_two(client, env, "hist2")
        self._order_merges(env, "dupe-hist2")

        r = client.get("/api/v1/customers/merges", headers=env["headers"])
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body) == {"items", "total", "limit", "offset"}
        assert body["total"] == 2
        assert body["limit"] == 50
        assert body["offset"] == 0
        assert len(body["items"]) == 2
        first = body["items"][0]
        assert set(first) == {
            "id", "survivor_id", "merged_id", "actor_user_id", "reason",
            "evidence", "reverted_at", "created_at",
        }
        # newest first: second merge (hist2) comes before the first (hist)
        assert first["reason"] == "dupe-hist2"
        assert first["reverted_at"] is None
        assert first["actor_user_id"] == str(env["admin_id"])
        assert "moved_method_ids" in first["evidence"]
        older = body["items"][1]
        assert older["survivor_id"] == survivor
        assert older["merged_id"] == merged

        # pagination window
        rp = client.get("/api/v1/customers/merges?limit=1&offset=1", headers=env["headers"])
        page = rp.json()
        assert page["total"] == 2
        assert page["limit"] == 1
        assert page["offset"] == 1
        assert len(page["items"]) == 1
        assert page["items"][0]["reason"] == "dupe-hist"

    def test_revert_flow_completes_against_history(self, client: TestClient, env) -> None:
        survivor, merged = self._merge_two(client, env, "rev")
        hist = client.get("/api/v1/customers/merges?limit=10", headers=env["headers"]).json()
        merge_row = next(i for i in hist["items"] if i["merged_id"] == merged)
        assert merge_row["reverted_at"] is None

        rv = client.post(
            f"/api/v1/customers/merges/{merge_row['id']}/revert", headers=env["headers"]
        )
        assert rv.status_code == 200, rv.text
        assert rv.json()["reverted_at"] is not None

        hist2 = client.get("/api/v1/customers/merges?limit=10", headers=env["headers"]).json()
        row2 = next(i for i in hist2["items"] if i["id"] == merge_row["id"])
        assert row2["reverted_at"] is not None

        # reverted contact is visible again and history-driven revert of the
        # same merge is refused
        detail = client.get(f"/api/v1/customers/{merged}", headers=env["headers"])
        assert detail.status_code == 200
        assert detail.json()["contact"]["status"] == "ACTIVE"
        again = client.post(
            f"/api/v1/customers/merges/{merge_row['id']}/revert", headers=env["headers"]
        )
        assert again.status_code == 409

    def test_merges_requires_manager_role(
        self, client: TestClient, env, user_factory, auth_headers
    ) -> None:
        buyer = user_factory(role=RoleName.BUYER, email=f"mh-{uuid4().hex[:8]}@ex.com")
        headers = auth_headers(buyer.email)
        r = client.get("/api/v1/customers/merges", headers=headers)
        assert r.status_code == 403

    def test_merges_is_tenant_scoped(self, client: TestClient, env) -> None:
        self._merge_two(client, env, "iso")
        other_tenant = Tenant(slug=f"mo-{uuid4().hex[:8]}", name="MO")
        with env["factory"]() as s:
            s.add(other_tenant)
            s.flush()
            c1 = Contact(
                tenant_id=other_tenant.id,
                canonical_key=f"uuid:{uuid4()}",
                display_name="O1",
            )
            c2 = Contact(
                tenant_id=other_tenant.id,
                canonical_key=f"uuid:{uuid4()}",
                display_name="O2",
            )
            s.add_all([c1, c2])
            s.flush()
            s.add(
                ContactMerge(
                    tenant_id=other_tenant.id,
                    survivor_id=c1.id,
                    merged_id=c2.id,
                    evidence={},
                )
            )
            s.commit()
        body = client.get(
            "/api/v1/customers/merges", headers=env["headers"]
        ).json()
        assert body["total"] == 1
        assert body["items"][0]["reason"] == "dupe-iso"

    def test_query_validation(self, client: TestClient, env) -> None:
        r = client.get("/api/v1/customers/merges?limit=0", headers=env["headers"])
        assert r.status_code == 422
        r2 = client.get("/api/v1/customers/merges?offset=-1", headers=env["headers"])
        assert r2.status_code == 422


class TestListEnrichment:
    """GET /customers list items gain primary_method + opportunities_count."""

    def test_counts_and_primary_method(self, client: TestClient, env) -> None:
        email = f"list-{uuid4().hex[:8]}@ex.com"
        phone = f"9{uuid4().int % 10**9:09d}"
        r = client.post(
            "/api/v1/customers/contacts",
            json={"display_name": "Listed", "email": email, "phone": f"+91{phone}"},
            headers=env["headers"],
        )
        contact_id = r.json()["contact"]["id"]
        with env["factory"]() as s:
            admin = s.get(User, env["admin_id"])
            service.open_opportunity(
                s, actor=admin, contact_id=UUID(contact_id), project_id=env["project_id"]
            )
            s.commit()

        r2 = client.get("/api/v1/customers", headers=env["headers"])
        assert r2.status_code == 200, r2.text
        items = {i["id"]: i for i in r2.json()["items"]}
        item = items[contact_id]
        assert item["opportunities_count"] == 1
        # primary method is the EMAIL (created first in resolve order)
        assert item["primary_method"]["kind"] == "EMAIL"
        assert item["primary_method"]["value"] == email

    def test_zero_count_and_no_method_for_manual_contact(
        self, client: TestClient, env
    ) -> None:
        with env["factory"]() as s:
            contact = Contact(
                tenant_id=env["tenant_id"],
                canonical_key=f"uuid:{uuid4()}",
                display_name="Methodless",
            )
            s.add(contact)
            s.commit()
            cid = str(contact.id)
        items = {i["id"]: i for i in client.get("/api/v1/customers", headers=env["headers"]).json()["items"]}
        assert items[cid]["opportunities_count"] == 0
        assert items[cid]["primary_method"] is None
