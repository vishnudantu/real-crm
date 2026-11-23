"""Booking cancellation policy engine tests (postsales.cancellation).

Matrix covered:
- Free-cancel window (default 7 days from booking): zero fee, everything
  collected recorded as refund-due.
- Late-cancel fee percent per stage (BOOKED / AGREEMENT_SIGNED /
  PAYMENTS_IN_PROGRESS) computed against live receipts.
- CLOSED bookings are rejected (409); already-CANCELLED cancels idempotently.
- CANCELLED releases the canonical unit (BOOKED -> AVAILABLE, CANCELLATION
  source event) and never voids or moves receipts silently.
- Cross-tenant and unknown bookings are 404; non-admin actors are 403.
- Tenant policy overrides are read from system settings; invalid values fall
  back to defaults; policy_check=False skips fee assessment.
- A configured sale.cancelled messaging trigger rule queues an outbox row.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.inventory.models import PropertyUnit, UnitEventSource, UnitStatus, UnitStatusEvent
from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.messaging.models import MessageDelivery, MessageTemplate, TriggerRule
from app.modules.postsales import service as postsales_service
from app.modules.postsales.cancellation import (
    DEFAULT_POLICY,
    FREE_WINDOW_DAYS,
    LATE_FEE_PERCENT_BY_STAGE,
    cancel_booking,
)
from app.modules.postsales.models import (
    PaymentPlanType,
    ReceiptChannel,
    Receipt,
    SaleStatus,
)
from app.modules.postsales.schemas import (
    InstallmentSpec,
    PaymentPlanCreateRequest,
    ReceiptCreateRequest,
    SaleBookingCreateRequest,
)
from app.modules.projects.models import Project, ProjectStatus
from app.modules.settings.repository import upsert_setting
from app.modules.tenancy.models import Tenant
from app.modules.users.exceptions import InsufficientPermissionsError
from app.modules.users.models import Role, RoleName, User
from app.modules.auth.security import hash_password
from tests.support import TEST_PASSWORD


def _fixture(
    session: Session,
    *,
    tenant_slug: str = "cancel-co",
    admin_email: str = "admin@cancel.example",
) -> tuple[Tenant, User, Project, Lead]:
    tenant = Tenant(slug=tenant_slug, name="Cancel Co")
    session.add(tenant)
    session.flush()
    role = session.scalar(select(Role).where(Role.name == RoleName.ADMIN.value))
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    admin = User(
        tenant_id=tenant.id, full_name="Admin", email=admin_email,
        password_hash=hash_password(TEST_PASSWORD), role_id=role.id, is_active=True,
    )
    session.add(admin)
    session.flush()
    project = Project(
        tenant_id=tenant.id, name=f"Tower {uuid4().hex[:6]}", slug=f"tower-{uuid4().hex[:8]}",
        location="Pune", status=ProjectStatus.ACTIVE.value, created_by=admin.id,
    )
    session.add(project)
    session.flush()
    lead = Lead(
        tenant_id=tenant.id, full_name="Cancel Buyer", email=f"buyer-{uuid4().hex[:8]}@example.com",
        phone="+919876500001", project_id=project.id, source=LeadSource.WEBSITE.value,
        status=LeadStatus.CONVERTED.value, consent_to_contact=True,
    )
    session.add(lead)
    session.commit()
    return tenant, admin, project, lead


PLAN = PaymentPlanCreateRequest(
    name="Simple",
    plan_type=PaymentPlanType.TIME_LINKED,
    installments=[
        InstallmentSpec(milestone="Booking amount", amount_paise=10_00_00_00, due_on=date.today()),
    ],
)
COLLECTED_Paise = 40_00_00  # 40% of the 10,000,000-paise consideration, partly paid


def _booked_with_receipts(session: Session, admin: User, lead: Lead):
    """Create a sale booking + plan and post a partial receipt; return all."""

    booking = postsales_service.create_booking(
        session,
        actor=admin,
        payload=SaleBookingCreateRequest(
            lead_id=lead.id, unit_number="C-101", consideration_paise=10_00_00_00
        ),
    )
    plan = postsales_service.create_plan(
        session, actor=admin, booking_id=booking.id, payload=PLAN
    )
    receipt = postsales_service.record_receipt(
        session,
        actor=admin,
        payload=ReceiptCreateRequest(
            installment_id=plan.installments[0].id,
            amount_paise=COLLECTED_Paise,
            channel=ReceiptChannel.NEFT,
            reference="CANCEL-TEST",
        ),
    )
    return booking, plan, receipt


def _age_booking(session: Session, booking, days: int) -> None:
    booking.created_at = datetime.now(UTC) - timedelta(days=days)
    session.add(booking)
    session.commit()


# --------------------------------------------------------------------------- #
# Policy defaults


def test_policy_defaults_are_sane() -> None:
    assert FREE_WINDOW_DAYS == 7
    assert LATE_FEE_PERCENT_BY_STAGE == {
        "BOOKED": 10.0,
        "AGREEMENT_SIGNED": 25.0,
        "PAYMENTS_IN_PROGRESS": 50.0,
    }
    assert DEFAULT_POLICY["free_cancel_days"] == 7


# --------------------------------------------------------------------------- #
# Free-cancel window


def test_cancel_within_free_window_charges_nothing(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, _project, lead = _fixture(session)
        booking, _plan, _receipt = _booked_with_receipts(session, admin, lead)

        result = cancel_booking(session, admin, booking.id, "Changed plans")

        assert result.status == SaleStatus.CANCELLED.value
        assert result.free_window is True
        assert result.fee_paise == 0
        assert result.collected_paise == COLLECTED_Paise
        assert result.refund_due_paise == COLLECTED_Paise
        assert result.refunds_issued_paise == 0
        session.refresh(booking)
        assert booking.status == SaleStatus.CANCELLED.value


# --------------------------------------------------------------------------- #
# Late fees per stage


@pytest.mark.parametrize(
    ("sale_status", "expected_fee"),
    [
        (SaleStatus.BOOKED, int(COLLECTED_Paise * 0.10)),
        (SaleStatus.AGREEMENT_SIGNED, int(COLLECTED_Paise * 0.25)),
        (SaleStatus.PAYMENTS_IN_PROGRESS, int(COLLECTED_Paise * 0.50)),
    ],
)
def test_late_cancel_fee_by_stage(
    test_session_factory: sessionmaker[Session],
    sale_status: SaleStatus,
    expected_fee: int,
) -> None:
    with test_session_factory() as session:
        _tenant, admin, _project, lead = _fixture(session)
        booking, _plan, _receipt = _booked_with_receipts(session, admin, lead)
        booking.status = sale_status.value
        session.add(booking)
        _age_booking(session, booking, days=30)

        result = cancel_booking(session, admin, booking.id, "Financing fell through")

        assert result.free_window is False
        assert result.stage == sale_status.value
        assert result.fee_paise == expected_fee
        assert result.refund_due_paise == COLLECTED_Paise - expected_fee
        # Money is never moved: the receipt stays live and un-voided.
        receipt = session.scalar(select(Receipt).where(Receipt.id == _receipt.id))
        assert receipt is not None and receipt.voided_at is None


def test_late_cancel_with_zero_collected_has_zero_fee(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, _project, lead = _fixture(session)
        booking = postsales_service.create_booking(
            session,
            actor=admin,
            payload=SaleBookingCreateRequest(
                lead_id=lead.id, unit_number="C-102", consideration_paise=10_00_00_00
            ),
        )
        _age_booking(session, booking, days=30)

        result = cancel_booking(session, admin, booking.id, "No payment made")

        assert result.collected_paise == 0
        assert result.fee_paise == 0
        assert result.refund_due_paise == 0


# --------------------------------------------------------------------------- #
# Terminal-state matrix


def test_cancel_closed_booking_is_rejected(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, _project, lead = _fixture(session)
        booking = postsales_service.create_booking(
            session,
            actor=admin,
            payload=SaleBookingCreateRequest(
                lead_id=lead.id, unit_number="C-103", consideration_paise=10_00_00_00
            ),
        )
        plan = postsales_service.create_plan(
            session, actor=admin, booking_id=booking.id,
            payload=PaymentPlanCreateRequest(
                name="Full",
                plan_type=PaymentPlanType.TIME_LINKED,
                installments=[
                    InstallmentSpec(milestone="Only demand", amount_paise=10_00_00_00, due_on=date.today()),
                ],
            ),
        )
        postsales_service.record_receipt(
            session,
            actor=admin,
            payload=ReceiptCreateRequest(
                installment_id=plan.installments[0].id,
                amount_paise=10_00_00_00,
                channel=ReceiptChannel.NEFT,
            ),
        )
        session.refresh(booking)
        assert booking.status == SaleStatus.CLOSED.value

        with pytest.raises(HTTPException) as excinfo:
            cancel_booking(session, admin, booking.id, "Too late")
        assert excinfo.value.status_code == 409


def test_repeated_cancel_is_idempotent(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, _project, lead = _fixture(session)
        booking, _plan, _receipt = _booked_with_receipts(session, admin, lead)

        first = cancel_booking(session, admin, booking.id, "First cancel")
        second = cancel_booking(session, admin, booking.id, "First cancel")

        assert first.fee_paise == second.fee_paise == 0
        assert second.refund_due_paise == first.refund_due_paise == COLLECTED_Paise
        # No second ledger or refund side effect: still exactly one live receipt.
        live = session.scalars(
            select(Receipt).where(
                Receipt.installment_id == _receipt.installment_id,
                Receipt.voided_at.is_(None),
            )
        ).all()
        assert len(live) == 1


# --------------------------------------------------------------------------- #
# Unit release wiring


def test_cancel_releases_booked_unit(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, project, lead = _fixture(session)
        unit = PropertyUnit(
            tenant_id=tenant.id, project_id=project.id, internal_code="C-UNIT-1",
            status=UnitStatus.BOOKED.value, saleable=True,
        )
        session.add(unit)
        session.commit()

        booking = postsales_service.create_booking(
            session,
            actor=admin,
            payload=SaleBookingCreateRequest(
                lead_id=lead.id, unit_number="C-UNIT-1", unit_id=unit.id,
                consideration_paise=10_00_00_00,
            ),
        )

        result = cancel_booking(session, admin, booking.id, "Release the unit")

        assert result.unit_release is not None
        assert result.unit_release["released"] is True
        assert result.unit_release["from_status"] == UnitStatus.BOOKED.value
        assert result.unit_release["to_status"] == UnitStatus.AVAILABLE.value
        session.refresh(unit)
        assert unit.status == UnitStatus.AVAILABLE.value
        event = session.scalar(
            select(UnitStatusEvent).where(
                UnitStatusEvent.unit_id == unit.id,
                UnitStatusEvent.source == UnitEventSource.CANCELLATION.value,
            )
        )
        assert event is not None
        assert event.to_status == UnitStatus.AVAILABLE.value


def test_cancel_without_unit_or_non_booked_unit_reports_release_state(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, project, lead = _fixture(session)
        plain = postsales_service.create_booking(
            session,
            actor=admin,
            payload=SaleBookingCreateRequest(
                lead_id=lead.id, unit_number="C-NO-UNIT", consideration_paise=10_00_00_00
            ),
        )
        result = cancel_booking(session, admin, plain.id, "No canonical unit")
        assert result.unit_release is None

        unit = PropertyUnit(
            tenant_id=tenant.id, project_id=project.id, internal_code="C-UNIT-2",
            status=UnitStatus.SOLD.value, saleable=True,
        )
        session.add(unit)
        session.commit()
        lead2 = Lead(
            tenant_id=tenant.id, full_name="Sold Unit Buyer", phone="+919876500002",
            project_id=project.id, source=LeadSource.WEBSITE.value,
            status=LeadStatus.CONVERTED.value, consent_to_contact=True,
        )
        session.add(lead2)
        session.commit()
        booking2 = postsales_service.create_booking(
            session,
            actor=admin,
            payload=SaleBookingCreateRequest(
                lead_id=lead2.id, unit_number="C-UNIT-2", unit_id=unit.id,
                consideration_paise=10_00_00_00,
            ),
        )
        result2 = cancel_booking(session, admin, booking2.id, "Unit already sold")
        assert result2.unit_release is not None
        assert result2.unit_release["released"] is False
        session.refresh(unit)
        assert unit.status == UnitStatus.SOLD.value


# --------------------------------------------------------------------------- #
# Tenancy and roles


def test_cancel_cross_tenant_booking_is_404(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, _project, lead = _fixture(session)
        booking, _plan, _receipt = _booked_with_receipts(session, admin, lead)

    with test_session_factory() as session:
        other_tenant, other_admin, _p2, _l2 = _fixture(
            session, tenant_slug="other-cancel-co", admin_email="admin@other.example"
        )
        with pytest.raises(HTTPException) as excinfo:
            cancel_booking(session, other_admin, booking.id, "Not yours")
        assert excinfo.value.status_code == 404


def test_cancel_requires_admin(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session)
        booking, _plan, _receipt = _booked_with_receipts(session, admin, lead)
        exec_role = session.scalar(
            select(Role).where(Role.name == RoleName.SALES_EXECUTIVE.value)
        )
        if exec_role is None:
            exec_role = Role(name=RoleName.SALES_EXECUTIVE.value)
            session.add(exec_role)
            session.flush()
        exec_user = User(
            tenant_id=tenant.id, full_name="Exec", email=f"exec-{uuid4().hex[:8]}@cancel.example",
            password_hash=hash_password(TEST_PASSWORD), role_id=exec_role.id, is_active=True,
        )
        session.add(exec_user)
        session.commit()

        with pytest.raises(InsufficientPermissionsError):
            cancel_booking(session, exec_user, booking.id, "Not allowed")


# --------------------------------------------------------------------------- #
# Tenant policy overrides


def test_tenant_policy_override_changes_window_and_fee(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session)
        booking, _plan, _receipt = _booked_with_receipts(session, admin, lead)
        upsert_setting(
            session,
            tenant_id=tenant.id,
            key="cancellation_policy",
            category="POSTSALES",
            value={
                "free_cancel_days": 3,
                "late_fee_percent": {"BOOKED": 20.0},
            },
        )
        session.commit()
        _age_booking(session, booking, days=5)

        result = cancel_booking(session, admin, booking.id, "Window was shorter")

        assert result.free_window is False
        assert result.fee_paise == int(COLLECTED_Paise * 0.20)
        assert result.policy["free_cancel_days"] == 3
        assert result.policy["late_fee_percent"]["BOOKED"] == 20.0


def test_invalid_tenant_policy_falls_back_to_defaults(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session)
        booking, _plan, _receipt = _booked_with_receipts(session, admin, lead)
        upsert_setting(
            session,
            tenant_id=tenant.id,
            key="cancellation_policy",
            category="POSTSALES",
            value={"free_cancel_days": -5, "late_fee_percent": {"BOOKED": 250.0}},
        )
        session.commit()
        _age_booking(session, booking, days=30)

        result = cancel_booking(session, admin, booking.id, "Bad config")

        assert result.policy == dict(DEFAULT_POLICY)
        assert result.fee_paise == int(COLLECTED_Paise * 0.10)


def test_policy_check_false_skips_fee_assessment(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, _project, lead = _fixture(session)
        booking, _plan, _receipt = _booked_with_receipts(session, admin, lead)
        _age_booking(session, booking, days=30)

        result = cancel_booking(
            session, admin, booking.id, "Goodwill waiver", policy_check=False
        )

        assert result.policy_applied is False
        assert result.fee_paise == 0
        assert result.refund_due_paise == COLLECTED_Paise


# --------------------------------------------------------------------------- #
# Messaging outbox wiring


def test_cancel_queues_configured_outbox_message(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session)
        booking, _plan, _receipt = _booked_with_receipts(session, admin, lead)
        template = MessageTemplate(
            tenant_id=tenant.id,
            name="Sale cancelled",
            channel="SMS",
            body="{first_name}, your booking for {unit_number} was cancelled.",
        )
        session.add(template)
        session.flush()
        session.add(
            TriggerRule(
                tenant_id=tenant.id,
                event="sale.cancelled",
                channel="SMS",
                template_id=template.id,
                enabled=True,
                delay_minutes=0,
            )
        )
        session.commit()

        result = cancel_booking(session, admin, booking.id, "Outbox check")
        assert result.outbox_queued >= 1

        delivery = session.scalar(
            select(MessageDelivery).where(
                MessageDelivery.tenant_id == tenant.id,
                MessageDelivery.event == "sale.cancelled",
                MessageDelivery.entity_id == booking.id,
            )
        )
        assert delivery is not None
        assert delivery.to_address == lead.phone


# --------------------------------------------------------------------------- #
# HTTP surface


@pytest.fixture()
def api_env(
    client: TestClient,
    user_factory: Callable[..., User],
    auth_headers: Callable[..., dict[str, str]],
    test_session_factory: sessionmaker[Session],
) -> dict:
    from tests.lead_support import create_lead
    from tests.project_support import create_project

    admin = user_factory(role=RoleName.ADMIN, email=f"cadmin-{uuid4().hex[:8]}@example.com")
    exec_user = user_factory(role=RoleName.SALES_EXECUTIVE, email=f"cexec-{uuid4().hex[:8]}@example.com")
    headers = auth_headers(admin.email)

    project = create_project(client, headers, name=f"Cancel API {uuid4().hex[:6]}")
    client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"status": ProjectStatus.ACTIVE.value},
        headers=headers,
    )
    lead = create_lead(
        client,
        project_id=project["id"],
        full_name="API Cancel Buyer",
        phone=f"+9198{uuid4().int % 100000000:08d}",
        consent_to_contact=True,
    )
    with test_session_factory() as session:
        db_lead = session.scalar(
            select(Lead).where(Lead.id == UUID(lead["id"]))
        )
        db_lead.status = LeadStatus.CONVERTED.value
        session.add(db_lead)
        session.commit()
    booking = client.post(
        "/api/v1/sales-bookings",
        json={
            "lead_id": lead["id"],
            "unit_number": "API-1",
            "consideration_paise": 10_00_00_00,
        },
        headers=headers,
    )
    assert booking.status_code == 201, booking.text
    return {
        "booking_id": booking.json()["id"],
        "admin_headers": headers,
        "exec_headers": auth_headers(exec_user.email),
    }


def test_cancel_endpoint_returns_breakdown_for_admin(
    client: TestClient, api_env: dict
) -> None:
    response = client.post(
        f"/api/v1/sales-bookings/{api_env['booking_id']}/cancel",
        json={"reason": "API cancel"},
        headers=api_env["admin_headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == SaleStatus.CANCELLED.value
    assert body["free_window"] is True
    assert body["fee_paise"] == 0
    assert body["refund_due_paise"] == 0

    detail = client.get(
        f"/api/v1/sales-bookings/{api_env['booking_id']}",
        headers=api_env["admin_headers"],
    )
    assert detail.json()["status"] == SaleStatus.CANCELLED.value


def test_cancel_endpoint_forbidden_for_non_admin(
    client: TestClient, api_env: dict
) -> None:
    response = client.post(
        f"/api/v1/sales-bookings/{api_env['booking_id']}/cancel",
        json={"reason": "Exec should not cancel"},
        headers=api_env["exec_headers"],
    )
    assert response.status_code == 403


def test_cancel_endpoint_cross_tenant_is_404(
    client: TestClient,
    api_env: dict,
    user_factory: Callable[..., User],
    auth_headers: Callable[..., dict[str, str]],
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        other_tenant = Tenant(slug=f"cancel-other-{uuid4().hex[:6]}", name="Other Cancel Co")
        session.add(other_tenant)
        session.commit()
        session.refresh(other_tenant)
    other_admin = user_factory(
        role=RoleName.ADMIN,
        email=f"cadmin2-{uuid4().hex[:8]}@example.com",
        tenant=other_tenant,
    )
    response = client.post(
        f"/api/v1/sales-bookings/{api_env['booking_id']}/cancel",
        json={"reason": "Not your tenant"},
        headers=auth_headers(other_admin.email),
    )
    assert response.status_code == 404
