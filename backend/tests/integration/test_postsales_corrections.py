"""Receipt reversals and operational installment correction guarantees."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.modules.auth.security import hash_password
from app.modules.documents import service as document_service
from app.modules.documents.models import DocumentStatus
from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.postsales import repository, service
from app.modules.postsales.models import (
    Installment,
    InstallmentStatus,
    PaymentPlanType,
    Receipt,
    ReceiptChannel,
    SaleBooking,
    SaleStatus,
)
from app.modules.postsales.schemas import (
    InstallmentSpec,
    InstallmentUpdateRequest,
    PaymentPlanCreateRequest,
    ReceiptCreateRequest,
    ReceiptVoidRequest,
    SaleBookingCreateRequest,
)
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD


def _fixture(session: Session, *, slug: str | None = None) -> tuple[Tenant, User, Project, Lead]:
    tenant = Tenant(slug=slug or f"correction-{uuid4().hex[:8]}", name="Correction Realty")
    session.add(tenant)
    session.flush()
    role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one_or_none()
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    admin = User(
        tenant_id=tenant.id,
        full_name="Correction Admin",
        email=f"correction.{uuid4().hex[:10]}@example.test",
        password_hash=hash_password(TEST_PASSWORD),
        role_id=role.id,
        is_active=True,
    )
    session.add(admin)
    session.flush()
    project = Project(
        tenant_id=tenant.id,
        name="Correction Heights",
        slug=f"correction-{uuid4().hex[:8]}",
        location="Pune",
        status=ProjectStatus.ACTIVE.value,
        created_by=admin.id,
    )
    session.add(project)
    session.flush()
    lead = Lead(
        tenant_id=tenant.id,
        full_name="Correction Buyer",
        email=f"buyer.{uuid4().hex[:10]}@example.test",
        phone=f"93{uuid4().int % 10**10:010d}",
        project_id=project.id,
        source=LeadSource.WEBSITE.value,
        status=LeadStatus.CONVERTED.value,
        consent_to_contact=True,
    )
    session.add(lead)
    session.commit()
    return tenant, admin, project, lead


def _plan(
    session: Session,
    admin: User,
    lead: Lead,
    *,
    due_on: date | None = None,
    amount_paise: int = 10_000,
):
    booking = service.create_booking(
        session,
        actor=admin,
        payload=SaleBookingCreateRequest(
            lead_id=lead.id,
            unit_number=f"C-{uuid4().hex[:6]}",
            consideration_paise=amount_paise,
        ),
    )
    plan = service.create_plan(
        session,
        actor=admin,
        booking_id=booking.id,
        payload=PaymentPlanCreateRequest(
            name="Correction schedule",
            plan_type=PaymentPlanType.TIME_LINKED,
            installments=[
                InstallmentSpec(
                    milestone="Completion",
                    amount_paise=amount_paise,
                    due_on=due_on or date.today() + timedelta(days=30),
                )
            ],
        ),
    )
    return booking, plan.installments[0]


def _receipt(
    session: Session,
    admin: User,
    installment_id,
    amount_paise: int,
    *,
    key: str | None = None,
) -> Receipt:
    return service.record_receipt(
        session,
        actor=admin,
        payload=ReceiptCreateRequest(
            installment_id=installment_id,
            amount_paise=amount_paise,
            channel=ReceiptChannel.UPI,
            idempotency_key=key,
        ),
    )


def _void_payload(reason: str = "Payment posted in error"):
    return ReceiptVoidRequest(reason=reason)


def test_void_is_idempotent_and_excluded_from_live_totals(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, _project, lead = _fixture(session)
        booking, installment = _plan(session, admin, lead, due_on=date.today())
        first = _receipt(session, admin, installment.id, 4_000, key="bank-original")
        second = _receipt(session, admin, installment.id, 3_000)

        voided = service.void_receipt(
            session, actor=admin, receipt_id=first.id, payload=_void_payload()
        )
        assert voided.id == first.id
        assert voided.amount_paise == 4_000
        assert voided.voided_at is not None
        assert voided.voided_by_id == admin.id
        assert voided.void_reason == "Payment posted in error"
        assert repository.receipt_total_for_installment(
            session, installment.id, tenant_id=admin.tenant_id
        ) == 3_000
        assert repository.paid_map_for_plan(
            session, [installment.plan_id], tenant_id=admin.tenant_id
        )[installment.id] == 3_000

        ledger = service.ledger(session, actor=admin, booking_id=booking.id)
        assert ledger["collected_paise"] == 3_000
        assert ledger["outstanding_paise"] == 7_000
        assert len(ledger["receipts"]) == 2

        with pytest.raises(HTTPException) as repeated:
            service.void_receipt(
                session, actor=admin, receipt_id=first.id,
                payload=_void_payload("Different correction reason"),
            )
        assert repeated.value.status_code == 409
        assert "Payment posted in error" in repeated.value.detail

        # A void never frees or changes the original idempotency key.
        replay = _receipt(session, admin, installment.id, 4_000, key="bank-original")
        assert replay.id == first.id
        replacement = _receipt(session, admin, installment.id, 4_000, key="bank-replacement")
        assert replacement.id != first.id
        assert replacement.receipt_number != first.receipt_number
        assert repository.receipt_total_for_installment(
            session, installment.id, tenant_id=admin.tenant_id
        ) == 7_000
        session.expire_all()
        assert session.get(Receipt, first.id).amount_paise == 4_000


@pytest.mark.parametrize(
    ("remaining_paid", "due_delta", "expected_status"),
    [
        (0, 30, InstallmentStatus.PENDING.value),
        (0, 0, InstallmentStatus.DUE.value),
        (0, -1, InstallmentStatus.OVERDUE.value),
        (4_000, -1, InstallmentStatus.PART_PAID.value),
    ],
)
def test_void_recomputes_installment_status_from_live_payments(
    test_session_factory: sessionmaker[Session],
    remaining_paid: int,
    due_delta: int,
    expected_status: str,
) -> None:
    with test_session_factory() as session:
        _tenant, admin, _project, lead = _fixture(session)
        _booking, installment = _plan(
            session, admin, lead, due_on=date.today() + timedelta(days=due_delta)
        )
        installment_id = installment.id
        if remaining_paid == 0:
            # One full receipt; voiding it returns the balance to zero.
            target = _receipt(session, admin, installment_id, 10_000)
        else:
            # Two receipts settle it; voiding the second leaves the remainder.
            _receipt(session, admin, installment_id, remaining_paid)
            target = _receipt(session, admin, installment_id, 10_000 - remaining_paid)

        service.void_receipt(
            session, actor=admin, receipt_id=target.id, payload=_void_payload()
        )
        session.expire_all()
        assert session.get(Installment, installment_id).status == expected_status


def test_void_reopens_closed_booking_and_cross_tenant_is_404(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant_a, admin_a, _project_a, lead_a = _fixture(session, slug="correction-a")
        booking, installment = _plan(session, admin_a, lead_a)
        receipt = _receipt(session, admin_a, installment.id, 10_000)
        booking_id, receipt_id = booking.id, receipt.id
        session.expire_all()
        assert session.get(SaleBooking, booking_id).status == SaleStatus.CLOSED.value

        service.void_receipt(
            session, actor=admin_a, receipt_id=receipt_id, payload=_void_payload()
        )
        session.expire_all()
        assert session.get(SaleBooking, booking_id).status == SaleStatus.PAYMENTS_IN_PROGRESS.value

        _tenant_b, admin_b, _project_b, _lead_b = _fixture(session, slug="correction-b")
        with pytest.raises(HTTPException) as missing:
            service.void_receipt(
                session, actor=admin_b, receipt_id=receipt_id, payload=_void_payload()
            )
        assert missing.value.status_code == 404
        session.expire_all()
        assert session.get(Receipt, receipt_id).voided_at is not None


def test_void_also_voids_issued_receipt_document(
    test_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("DOCUMENTS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with test_session_factory() as session:
            _tenant, admin, _project, lead = _fixture(session)
            _booking, installment = _plan(session, admin, lead)
            receipt = _receipt(session, admin, installment.id, 1_000)
            document = document_service.issue_receipt_pdf(
                session, actor=admin, receipt_id=receipt.id
            )
            assert document.status == DocumentStatus.ISSUED.value

            service.void_receipt(
                session, actor=admin, receipt_id=receipt.id, payload=_void_payload()
            )
            session.expire_all()
            documents = document_service.list_documents(
                session, tenant_id=admin.tenant_id, reference_id=receipt.id
            )
            assert len(documents) == 1
            assert documents[0].status == DocumentStatus.VOIDED.value
            assert documents[0].void_reason == "Payment posted in error"
    finally:
        get_settings.cache_clear()


def test_installment_edit_validates_amount_and_status_and_reopens_booking(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, _project, lead = _fixture(session)
        booking, installment = _plan(session, admin, lead)
        _receipt(session, admin, installment.id, 10_000)
        booking_id, installment_id = booking.id, installment.id
        session.expire_all()
        assert session.get(SaleBooking, booking_id).status == SaleStatus.CLOSED.value

        with pytest.raises(HTTPException) as below_paid:
            service.update_installment(
                session, actor=admin, installment_id=installment_id,
                payload=InstallmentUpdateRequest(amount_paise=9_999),
            )
        assert below_paid.value.status_code == 400

        with pytest.raises(HTTPException) as forced_paid:
            service.update_installment(
                session, actor=admin, installment_id=installment_id,
                payload=InstallmentUpdateRequest(status=InstallmentStatus.PAID),
            )
        assert forced_paid.value.status_code == 400

        updated = service.update_installment(
            session, actor=admin, installment_id=installment_id,
            payload=InstallmentUpdateRequest(
                amount_paise=12_000,
                due_on=date.today() - timedelta(days=1),
                status=InstallmentStatus.DUE,
            ),
        )
        assert updated.status == InstallmentStatus.PART_PAID.value
        assert updated.due_on == date.today() - timedelta(days=1)
        session.expire_all()
        assert session.get(SaleBooking, booking_id).status == SaleStatus.PAYMENTS_IN_PROGRESS.value


@pytest.mark.parametrize(
    ("amount_paid", "new_amount", "due_delta", "expected_status"),
    [
        (4_000, 4_000, 30, InstallmentStatus.PAID.value),
        (4_000, 8_000, 30, InstallmentStatus.PART_PAID.value),
        (4_000, 8_000, -1, InstallmentStatus.PART_PAID.value),
        (0, 8_000, 0, InstallmentStatus.DUE.value),
        (0, 8_000, -1, InstallmentStatus.OVERDUE.value),
        (0, 8_000, 30, InstallmentStatus.PENDING.value),
    ],
)
def test_installment_amount_and_due_date_edits_recompute_status(
    test_session_factory: sessionmaker[Session],
    amount_paid: int,
    new_amount: int,
    due_delta: int,
    expected_status: str,
) -> None:
    with test_session_factory() as session:
        _tenant, admin, _project, lead = _fixture(session)
        _booking, installment = _plan(session, admin, lead)
        if amount_paid:
            _receipt(session, admin, installment.id, amount_paid)

        updated = service.update_installment(
            session, actor=admin, installment_id=installment.id,
            payload=InstallmentUpdateRequest(
                amount_paise=new_amount,
                due_on=date.today() + timedelta(days=due_delta),
            ),
        )
        assert updated.status == expected_status


def test_receipt_and_installment_api_roles_routing_and_validation(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    user_factory: Callable[..., User],
) -> None:
    with test_session_factory() as session:
        tenant = Tenant(slug="correction-api", name="Correction API")
        session.add(tenant)
        session.flush()
        admin = user_factory(role=RoleName.ADMIN, tenant=tenant, email="admin@correction.example")
        user_factory(role=RoleName.SALES_EXECUTIVE, tenant=tenant, email="sales@correction.example")
        user_factory(role=RoleName.BUYER, tenant=tenant, email="buyer@correction.example")
        admin = session.get(User, admin.id)
        project = Project(
            tenant_id=tenant.id, name="API corrections", slug="api-corrections", location="Pune",
            status=ProjectStatus.ACTIVE.value, created_by=admin.id,
        )
        session.add(project)
        session.flush()
        lead = Lead(
            tenant_id=tenant.id, full_name="API Buyer", email="api-buyer@correction.example",
            phone="+919800000019", project_id=project.id, source=LeadSource.WEBSITE.value,
            status=LeadStatus.CONVERTED.value, consent_to_contact=True,
        )
        session.add(lead)
        session.commit()
        _booking, installment = _plan(session, admin, lead)
        receipt = _receipt(session, admin, installment.id, 1_000)
        receipt_id, installment_id = str(receipt.id), str(installment.id)

    def login(email: str) -> dict[str, str]:
        response = client.post(
            "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    admin_headers = login("admin@correction.example")
    sales_headers = login("sales@correction.example")
    buyer_headers = login("buyer@correction.example")
    detail = client.get(f"/api/v1/sales-bookings/receipts/{receipt_id}", headers=sales_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["voided_at"] is None
    assert client.get(f"/api/v1/sales-bookings/receipts/{receipt_id}", headers=buyer_headers).status_code == 403
    assert client.post(
        f"/api/v1/sales-bookings/receipts/{receipt_id}/void",
        headers=sales_headers, json={"reason": "Not permitted"},
    ).status_code == 403
    assert client.post(
        f"/api/v1/sales-bookings/receipts/{receipt_id}/void",
        headers=admin_headers, json={"reason": "no"},
    ).status_code == 422
    assert client.patch(
        f"/api/v1/sales-bookings/installments/{installment_id}",
        headers=sales_headers, json={"status": "PAID"},
    ).status_code == 403

    patched = client.patch(
        f"/api/v1/sales-bookings/installments/{installment_id}",
        headers=admin_headers,
        json={"amount_paise": 2_000, "due_on": str(date.today() - timedelta(days=1))},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "PART_PAID"
    assert patched.json()["paid_paise"] == 1_000
    assert patched.json()["outstanding_paise"] == 1_000

    voided = client.post(
        f"/api/v1/sales-bookings/receipts/{receipt_id}/void",
        headers=admin_headers, json={"reason": "Bank rejected this payment"},
    )
    assert voided.status_code == 200, voided.text
    assert voided.json()["void_reason"] == "Bank rejected this payment"
    repeated = client.post(
        f"/api/v1/sales-bookings/receipts/{receipt_id}/void",
        headers=admin_headers, json={"reason": "Another reason"},
    )
    assert repeated.status_code == 409
    assert "Bank rejected this payment" in repeated.text


def test_installment_patch_cannot_force_terminal_status(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, _project, lead = _fixture(session)
        _booking, installment = _plan(session, admin, lead)
        for target in (InstallmentStatus.PAID, InstallmentStatus.WAIVED):
            with pytest.raises(HTTPException) as rejected:
                service.update_installment(
                    session, actor=admin, installment_id=installment.id,
                    payload=InstallmentUpdateRequest(status=target),
                )
            assert rejected.value.status_code == 400


def test_waived_installment_is_not_editable_through_this_route(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, _project, lead = _fixture(session)
        _booking, installment = _plan(session, admin, lead)
        installment.status = InstallmentStatus.WAIVED.value
        session.add(installment)
        session.commit()

        with pytest.raises(HTTPException) as rejected:
            service.update_installment(
                session, actor=admin, installment_id=installment.id,
                payload=InstallmentUpdateRequest(amount_paise=5_000),
            )
        assert rejected.value.status_code == 400
