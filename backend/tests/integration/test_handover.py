"""Handover readiness, possession controls, buyer visibility and outbox."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.customers.models import (
    Contact,
    ContactMethod,
    ContactMethodKind,
    ContactStatus,
    Opportunity,
    OpportunityStage,
    VerificationState,
)
from app.modules.handover.models import HandoverCase, KeyHandover
from app.modules.inventory.models import PropertyUnit, UnitStatus
from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.messaging.consent import evaluate
from app.modules.messaging.models import MessageDelivery, MessageTemplate, TriggerRule
from app.modules.postsales.models import (
    Installment,
    InstallmentStatus,
    PaymentPlan,
    PaymentPlanType,
    Receipt,
    ReceiptChannel,
    SaleBooking,
    SaleStatus,
)
from app.modules.projects.models import Project, ProjectStatus
from app.modules.settings.models import AuditLog
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName

API = "/api/v1/handover"


@pytest.fixture()
def env(
    client: TestClient,
    override_db: None,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> dict:
    admin = user_factory(role=RoleName.ADMIN)
    manager = user_factory(role=RoleName.MANAGER)
    sales = user_factory(role=RoleName.SALES_EXECUTIVE)
    buyer = user_factory(role=RoleName.BUYER, email="handover-buyer@example.com")
    outsider_tenant = Tenant(slug=f"handover-other-{uuid4().hex[:8]}", name="Other")
    with test_session_factory() as session:
        session.add(outsider_tenant)
        session.commit()
    outsider = user_factory(role=RoleName.ADMIN, tenant=outsider_tenant)
    with test_session_factory() as session:
        project = Project(
            tenant_id=admin.tenant_id,
            name="Handover Heights",
            slug=f"handover-{uuid4().hex[:8]}",
            location="Bengaluru",
            status=ProjectStatus.ACTIVE.value,
            created_by=admin.id,
        )
        session.add(project)
        session.flush()
        unit = PropertyUnit(
            tenant_id=admin.tenant_id,
            project_id=project.id,
            internal_code="A-101",
            status=UnitStatus.BOOKED.value,
        )
        session.add(unit)
        session.flush()
        lead = Lead(
            tenant_id=admin.tenant_id,
            full_name="Handover Buyer",
            email=buyer.email,
            phone="+919876543210",
            project_id=project.id,
            source=LeadSource.WEBSITE.value,
            status=LeadStatus.CONVERTED.value,
            consent_to_contact=True,
        )
        session.add(lead)
        session.flush()
        booking = SaleBooking(
            tenant_id=admin.tenant_id,
            lead_id=lead.id,
            project_id=project.id,
            unit_id=unit.id,
            unit_number=unit.internal_code,
            consideration_paise=1_000_000,
            status=SaleStatus.AGREEMENT_SIGNED.value,
            agreement_date=date.today(),
            expected_possession=date.today() + timedelta(days=7),
        )
        session.add(booking)
        session.flush()
        plan = PaymentPlan(
            tenant_id=admin.tenant_id,
            sale_booking_id=booking.id,
            name="Final plan",
            plan_type=PaymentPlanType.TIME_LINKED.value,
            is_active=True,
        )
        session.add(plan)
        session.flush()
        installment = Installment(
            tenant_id=admin.tenant_id,
            plan_id=plan.id,
            sequence_no=1,
            milestone="Final payment",
            amount_paise=1_000_000,
            due_on=date.today(),
            status=InstallmentStatus.DUE.value,
        )
        session.add(installment)
        contact = Contact(
            tenant_id=admin.tenant_id,
            canonical_key=f"email:{buyer.email}",
            display_name=buyer.full_name,
            status=ContactStatus.ACTIVE.value,
        )
        session.add(contact)
        session.flush()
        session.add_all([
            ContactMethod(
                tenant_id=admin.tenant_id,
                contact_id=contact.id,
                kind=ContactMethodKind.EMAIL.value,
                value=buyer.email,
                normalized_value=buyer.email,
                verification_state=VerificationState.VERIFIED.value,
                provenance={},
                is_primary=True,
            ),
            Opportunity(
                tenant_id=admin.tenant_id,
                contact_id=contact.id,
                project_id=project.id,
                lead_id=lead.id,
                stage=OpportunityStage.BOOKED.value,
            ),
        ])
        session.commit()
        return {
            "tenant_id": admin.tenant_id,
            "unit_id": unit.id,
            "booking_id": booking.id,
            "installment_id": installment.id,
            "admin_id": admin.id,
            "manager_id": manager.id,
            "admin": auth_headers(admin.email),
            "manager": auth_headers(manager.email),
            "sales": auth_headers(sales.email),
            "buyer": auth_headers(buyer.email),
            "outsider": auth_headers(outsider.email),
        }


def _receipt(session: Session, env: dict, *, voided: bool = False) -> Receipt:
    receipt = Receipt(
        tenant_id=env["tenant_id"],
        installment_id=env["installment_id"],
        receipt_number=f"HAND-{uuid4().hex[:10]}",
        amount_paise=1_000_000,
        channel=ReceiptChannel.NEFT.value,
        voided_at=datetime.now(UTC) if voided else None,
    )
    session.add(receipt)
    session.commit()
    return receipt


def _create_case(client: TestClient, env: dict, **overrides) -> dict:
    payload = {
        "unit_id": str(env["unit_id"]),
        "booking_id": str(env["booking_id"]),
        "registration_date": str(date.today()),
    }
    payload.update(overrides)
    response = client.post(f"{API}/cases", json=payload, headers=env["admin"])
    assert response.status_code == 201, response.text
    return response.json()


def _pay_and_create_ready_case(factory: sessionmaker[Session], client: TestClient, env: dict) -> dict:
    with factory() as session:
        _receipt(session, env)
    return _create_case(client, env)


def _add_snag(client: TestClient, env: dict, case_id: str, **overrides) -> dict:
    payload = {"room": "Kitchen", "description": "Tap leaks", "severity": "MINOR"}
    payload.update(overrides)
    response = client.post(
        f"{API}/cases/{case_id}/snags", json=payload, headers=env["admin"]
    )
    assert response.status_code == 201, response.text
    return response.json()


def _snag_action(client: TestClient, env: dict, snag_id: str, action: str, actor="admin"):
    return client.post(
        f"{API}/snags/{snag_id}/{action}", json={}, headers=env[actor]
    )


def test_readiness_uses_live_money_excludes_voided_and_blocks_completion(
    client: TestClient, env: dict, test_session_factory: sessionmaker[Session]
) -> None:
    case = _create_case(client, env)
    checklist = client.get(f"{API}/cases/{case['id']}/checklist", headers=env["sales"])
    assert checklist.status_code == 200, checklist.text
    body = checklist.json()
    assert body["score"] == 80
    assert body["financials"]["outstanding_paise"] == 1_000_000
    assert [row["code"] for row in body["blockers"]] == ["FINANCIALS"]

    blocked = client.post(f"{API}/cases/{case['id']}/complete", json={}, headers=env["manager"])
    assert blocked.status_code == 409
    assert "FINANCIALS" in blocked.text
    assert "80%" in blocked.text

    with test_session_factory() as session:
        _receipt(session, env, voided=True)
    still_blocked = client.get(f"{API}/cases/{case['id']}/checklist", headers=env["sales"]).json()
    assert still_blocked["score"] == 80
    assert still_blocked["financials"]["outstanding_paise"] == 1_000_000

    with test_session_factory() as session:
        _receipt(session, env)
    ready = client.get(f"{API}/cases/{case['id']}/checklist", headers=env["sales"]).json()
    assert ready["score"] == 100
    assert ready["blockers"] == []
    assert ready["financials"]["collected_paise"] == 1_000_000


def test_state_machine_order_and_verified_snags_gate_completion(
    client: TestClient, env: dict, test_session_factory: sessionmaker[Session]
) -> None:
    case = _pay_and_create_ready_case(test_session_factory, client, env)
    snag = _add_snag(client, env, case["id"])
    checklist = client.get(f"{API}/cases/{case['id']}/checklist", headers=env["sales"]).json()
    assert checklist["score"] == 80
    assert checklist["blockers"][0]["code"] == "SNAGS"
    assert _snag_action(client, env, snag["id"], "verify").status_code == 409

    fixed = _snag_action(client, env, snag["id"], "fix", "manager")
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["status"] == "FIXED"
    assert fixed.json()["fixed_by_id"] == str(env["manager_id"])

    verified = _snag_action(client, env, snag["id"], "verify", "admin")
    assert verified.status_code == 200, verified.text
    assert verified.json()["status"] == "VERIFIED"
    assert _snag_action(client, env, snag["id"], "close", "manager").status_code == 200
    assert client.post(f"{API}/cases/{case['id']}/complete", json={}, headers=env["manager"]).status_code == 200
    assert client.post(f"{API}/cases/{case['id']}/complete", json={}, headers=env["manager"]).status_code == 409


def test_snag_fixer_cannot_verify_own_work(
    client: TestClient, env: dict, test_session_factory: sessionmaker[Session]
) -> None:
    case = _pay_and_create_ready_case(test_session_factory, client, env)
    snag = _add_snag(client, env, case["id"])
    _snag_action(client, env, snag["id"], "fix", "manager")
    response = _snag_action(client, env, snag["id"], "verify", "manager")
    assert response.status_code == 409
    assert "different staff member" in response.text
    still_unverified = client.get(
        f"{API}/cases/{case['id']}/checklist", headers=env["sales"]
    ).json()
    assert still_unverified["score"] == 80


def test_sales_read_only_buyer_only_sees_own_snags_and_cross_tenant_is_404(
    client: TestClient, env: dict, test_session_factory: sessionmaker[Session]
) -> None:
    case = _create_case(client, env)
    snag = _add_snag(client, env, case["id"], room="Bathroom", description="Tile cracked")
    assert client.post(f"{API}/cases", json={"unit_id": str(env["unit_id"])}, headers=env["sales"]).status_code == 403
    assert client.get(f"{API}/cases/{case['id']}", headers=env["outsider"]).status_code == 404
    assert client.get(f"{API}/cases/{case['id']}", headers=env["buyer"]).status_code == 403

    listing = client.get(f"{API}/mine", headers=env["buyer"])
    assert listing.status_code == 200, listing.text
    assert len(listing.json()["items"]) == 1
    assert listing.json()["items"][0]["snags"] == [{
        "id": snag["id"], "room": "Bathroom", "description": "Tile cracked",
        "severity": "MINOR", "status": "OPEN", "photo_evidence_path": None,
    }]
    assert "outstanding_paise" not in listing.text

    other_tenant = Tenant(slug=f"foreign-buyer-{uuid4().hex[:8]}", name="Foreign buyer tenant")
    with test_session_factory() as session:
        session.add(other_tenant)
        session.flush()
        project = Project(
            tenant_id=other_tenant.id, name="Foreign project", slug=f"foreign-{uuid4().hex[:8]}",
            location="Elsewhere", status=ProjectStatus.ACTIVE.value, created_by=env["admin_id"],
        )
        session.add(project)
        session.flush()
        foreign_unit = PropertyUnit(
            tenant_id=other_tenant.id, project_id=project.id,
            internal_code="Z-999", status=UnitStatus.BOOKED.value,
        )
        session.add(foreign_unit)
        session.flush()
        foreign_case = HandoverCase(tenant_id=other_tenant.id, unit_id=foreign_unit.id)
        session.add(foreign_case)
        session.commit()
        foreign_case_id = foreign_case.id
    assert client.get(f"{API}/mine?case_id={foreign_case_id}", headers=env["buyer"]).status_code == 200
    assert len(client.get(f"{API}/mine?case_id={foreign_case_id}", headers=env["buyer"]).json()["items"]) == 1


def test_registration_possession_and_missing_booking_fail_honestly(
    client: TestClient, env: dict, test_session_factory: sessionmaker[Session]
) -> None:
    with test_session_factory() as session:
        booking = session.get(SaleBooking, env["booking_id"])
        booking.status = SaleStatus.BOOKED.value
        booking.agreement_date = None
        booking.expected_possession = None
        session.commit()
        _receipt(session, env)
    case = _create_case(client, env, registration_date=None)
    body = client.get(f"{API}/cases/{case['id']}/checklist", headers=env["sales"]).json()
    assert body["score"] == 40
    assert {row["code"] for row in body["blockers"]} == {"AGREEMENT", "REGISTRATION", "POSSESSION"}

    with test_session_factory() as session:
        second_unit = PropertyUnit(
            tenant_id=env["tenant_id"], project_id=booking.project_id,
            internal_code="A-102", status=UnitStatus.AVAILABLE.value,
        )
        session.add(second_unit)
        session.commit()
        second_unit_id = second_unit.id
    without_booking = client.post(
        f"{API}/cases", json={"unit_id": str(second_unit_id)}, headers=env["admin"]
    )
    assert without_booking.status_code == 201, without_booking.text
    body = client.get(f"{API}/cases/{without_booking.json()['id']}/checklist", headers=env["sales"]).json()
    assert body["score"] == 0
    assert body["blockers"][0]["code"] == "BOOKING"
    assert body["blockers"][0]["required_count"] == 5


def test_completion_override_is_on_row_and_audit_and_key_register_works(
    client: TestClient, env: dict, test_session_factory: sessionmaker[Session]
) -> None:
    case = _create_case(client, env)
    key = client.post(
        f"{API}/cases/{case['id']}/keys",
        json={"keys_count": 3, "cards_count": 1, "handed_to_name": "Handover Buyer", "notes": "ID checked"},
        headers=env["manager"],
    )
    assert key.status_code == 201, key.text
    assert key.json()["handed_at"] is not None
    key_id = key.json()["id"]
    collected = client.post(
        f"{API}/keys/{key_id}/collect", json={"notes": "Received by buyer"}, headers=env["manager"]
    )
    assert collected.status_code == 200, collected.text
    assert collected.json()["collected_id"] == str(env["manager_id"])

    response = client.post(
        f"{API}/cases/{case['id']}/complete",
        json={"override_reason": "Managing director approved exceptional early possession."},
        headers=env["manager"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "HANDED_OVER"
    assert response.json()["override_reason"].startswith("Managing director")
    with test_session_factory() as session:
        stored = session.get(HandoverCase, UUID(case["id"]))
        assert stored is not None and stored.override_by_id == env["manager_id"]
        assert stored.override_at is not None
        assert stored.handed_over_by_id == env["manager_id"]
        assert stored.handed_over_at is not None
        assert stored.readiness["score"] == 80
        assert stored.readiness["blockers"][0]["code"] == "FINANCIALS"
        assert session.get(KeyHandover, UUID(key_id)) is not None
        collected_key = session.get(KeyHandover, UUID(key_id))
        assert collected_key.collected_at is not None
        assert collected_key.collected_notes == "Received by buyer"
        audit = session.scalar(
            select(AuditLog).where(
                AuditLog.action == "COMPLETE_HANDOVER", AuditLog.resource_id == case["id"]
            )
        )
        assert audit is not None
        assert audit.details["override_reason"].startswith("Managing director")
        assert [row["code"] for row in audit.details["blockers"]] == ["FINANCIALS"]


def test_photo_evidence_storage_permissions_and_download_isolation(
    client: TestClient, env: dict, test_session_factory: sessionmaker[Session], tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("VISIT_EVIDENCE_STORAGE_DIR", str(tmp_path))
    from app.core.config import get_settings
    get_settings.cache_clear()
    try:
        case = _create_case(client, env)
        snag = _add_snag(client, env, case["id"])
        upload = client.post(
            f"{API}/snags/{snag['id']}/photo", content=b"image evidence",
            headers={**env["manager"], "Content-Type": "image/png"},
        )
        assert upload.status_code == 200, upload.text
        photo_path = upload.json()["photo_evidence_path"]
        assert photo_path.startswith(f"{env['tenant_id']}/")
        assert (tmp_path / photo_path).read_bytes() == b"image evidence"
        download = client.get(f"{API}/snags/{snag['id']}/photo", headers=env["sales"])
        assert download.status_code == 200 and download.content == b"image evidence"
        buyer_download = client.get(f"{API}/mine/snags/{snag['id']}/photo", headers=env["buyer"])
        assert buyer_download.status_code == 200 and buyer_download.content == b"image evidence"
        assert client.get(f"{API}/snags/{snag['id']}/photo", headers=env["outsider"]).status_code == 404
        assert client.get(f"{API}/mine/snags/{snag['id']}/photo", headers=env["outsider"]).status_code == 403
        assert client.post(
            f"{API}/snags/{snag['id']}/photo", content=b"bad",
            headers={**env["manager"], "Content-Type": "text/plain"},
        ).status_code == 400
        assert client.delete(f"{API}/snags/{snag['id']}", headers=env["manager"]).status_code == 204
        assert not (tmp_path / photo_path).exists()
    finally:
        get_settings.cache_clear()


def test_consent_opt_out_suppresses_completed_handover(
    client: TestClient, env: dict, test_session_factory: sessionmaker[Session]
) -> None:
    with test_session_factory() as session:
        template = MessageTemplate(tenant_id=env["tenant_id"], name="Possession", channel="SMS", body="Done")
        session.add(template)
        session.flush()
        session.add(TriggerRule(
            tenant_id=env["tenant_id"], event="handover.completed", channel="SMS",
            template_id=template.id, enabled=True, delay_minutes=0,
        ))
        lead = session.scalar(select(Lead).where(Lead.project_id == session.get(SaleBooking, env["booking_id"]).project_id))
        lead.opted_out = True
        session.commit()
        case = _pay_and_create_ready_case(test_session_factory, client, env)
    assert client.post(f"{API}/cases/{case['id']}/complete", json={}, headers=env["admin"]).status_code == 200
    with test_session_factory() as session:
        delivery = session.scalar(select(MessageDelivery).where(MessageDelivery.event == "handover.completed"))
        assert delivery is not None
        decision = evaluate(session, delivery=delivery)
        assert decision.allowed is False and decision.reason == "RECIPIENT_OPTED_OUT"


def test_consented_completion_emits_transactional_outbox_once(
    client: TestClient, env: dict, test_session_factory: sessionmaker[Session]
) -> None:
    with test_session_factory() as session:
        template = MessageTemplate(
            tenant_id=env["tenant_id"], name="Possession", channel="SMS",
            body="Your keys for {unit_number} are ready.",
        )
        session.add(template)
        session.flush()
        session.add(TriggerRule(
            tenant_id=env["tenant_id"], event="handover.completed", channel="SMS",
            template_id=template.id, enabled=True, delay_minutes=0,
        ))
        session.commit()
        case = _pay_and_create_ready_case(test_session_factory, client, env)
    response = client.post(f"{API}/cases/{case['id']}/complete", json={}, headers=env["admin"])
    assert response.status_code == 200, response.text
    with test_session_factory() as session:
        deliveries = session.scalars(select(MessageDelivery).where(
            MessageDelivery.event == "handover.completed", MessageDelivery.entity_id == UUID(case["id"])
        )).all()
        assert len(deliveries) == 1
        assert deliveries[0].to_address == "+919876543210"
        assert evaluate(session, delivery=deliveries[0]).allowed is True
        keys = session.scalars(select(KeyHandover).where(KeyHandover.case_id == UUID(case["id"]))).all()
        assert keys == []


def test_cancelled_booking_blocks_agreement_gate_and_completion(
    client: TestClient, env: dict, test_session_factory: sessionmaker[Session]
) -> None:
    case = _pay_and_create_ready_case(test_session_factory, client, env)
    with test_session_factory() as session:
        booking = session.get(SaleBooking, env["booking_id"])
        booking.status = SaleStatus.CANCELLED.value
        # Stale agreement_date must NOT pass the gate after cancellation.
        session.commit()
    body = client.get(f"{API}/cases/{case['id']}/checklist", headers=env["sales"]).json()
    agreement = next(c for c in body["conditions"] if c["code"] == "AGREEMENT")
    assert agreement["met"] is False
    assert "cancelled" in agreement["detail"].lower()
    assert body["score"] < 100
    response = client.post(f"{API}/cases/{case['id']}/complete", json={"override_reason": "Trying to bypass."}, headers=env["admin"])
    assert response.status_code == 409
    assert "cancelled" in response.text.lower()


def test_no_op_case_patch_does_not_write_audit(
    client: TestClient, env: dict, test_session_factory: sessionmaker[Session]
) -> None:
    case = _create_case(client, env)
    response = client.patch(f"{API}/cases/{case['id']}", json={}, headers=env["admin"])
    assert response.status_code == 200
    with test_session_factory() as session:
        count = len(session.scalars(select(AuditLog).where(
            AuditLog.action == "UPDATE_HANDOVER_CHECKLIST", AuditLog.resource_id == case["id"]
        )).all())
        assert count == 0


def test_buyer_assignee_rejected(
    client: TestClient, env: dict, test_session_factory: sessionmaker[Session], user_factory
) -> None:
    buyer_user = user_factory(role=RoleName.BUYER, email=f"assignee-{uuid4().hex[:6]}@example.com")
    case = _create_case(client, env)
    response = client.post(
        f"{API}/cases/{case['id']}/snags",
        json={"room": "Hall", "description": "Wall crack", "severity": "MINOR", "assigned_user_id": str(buyer_user.id)},
        headers=env["admin"],
    )
    assert response.status_code == 404
    assert "staff" in response.text.lower()
