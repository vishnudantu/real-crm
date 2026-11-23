"""Post-sales pack tests: bookings, plans, demand letters, receipts, brokers."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.approvals.models import ApprovalRequest, ApprovalStatus
from app.modules.postsales import service
from app.modules.postsales.exceptions import (
    PaymentPlanAmountMismatchError,
    ReceiptAmountExceedsOutstandingError,
    SaleBookingExistsError,
)
from app.modules.postsales.models import (
    CommissionStatus,
    InstallmentStatus,
    PaymentPlanType,
    ReceiptChannel,
    SaleStatus,
)
from app.modules.postsales.schemas import (
    BrokerCommissionCreateRequest,
    InstallmentSpec,
    PaymentPlanCreateRequest,
    ReceiptCreateRequest,
    SaleBookingCreateRequest,
)
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from app.modules.auth.security import hash_password
from tests.support import TEST_PASSWORD


def _fixture(session: Session) -> tuple[Tenant, User, Project, Lead]:
    tenant = Tenant(slug="sales-co", name="Sales Co")
    session.add(tenant)
    session.flush()
    role = Role(name="ADMIN")
    session.add(role)
    session.flush()
    admin = User(
        tenant_id=tenant.id, full_name="Admin", email="a@sales.example",
        password_hash=hash_password(TEST_PASSWORD), role_id=role.id, is_active=True,
    )
    session.add(admin)
    session.flush()  # assign admin.id before referencing it in the project FK
    project = Project(
        tenant_id=tenant.id, name="Tower", slug="tower", location="Pune",
        status=ProjectStatus.ACTIVE.value, created_by=admin.id,
    )
    session.add(project)
    session.flush()
    lead = Lead(
        tenant_id=tenant.id, full_name="Buyer One", email="buyer@sales.example",
        phone="+919800000001", project_id=project.id, source=LeadSource.WEBSITE.value,
        status=LeadStatus.CONVERTED.value, consent_to_contact=True,
    )
    session.add(lead)
    session.commit()
    return tenant, admin, project, lead


def test_sale_booking_lifecycle_with_plan_partial_and_final_payments(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, project, lead = _fixture(session)

        booking = service.create_booking(
            session,
            actor=admin,
            payload=SaleBookingCreateRequest(
                lead_id=lead.id,
                unit_number="B-1201",
                configuration="3 BHK",
                carpet_area_sqft=1450,
                consideration_paise=1_50_00_00_00,  # ₹1.50 Cr
            ),
        )
        assert booking.status == SaleStatus.BOOKED.value

        with pytest.raises(SaleBookingExistsError):
            service.create_booking(
                session,
                actor=admin,
                payload=SaleBookingCreateRequest(
                    lead_id=lead.id, unit_number="B-1202", consideration_paise=1000
                ),
            )

        plan = service.create_plan(
            session,
            actor=admin,
            booking_id=booking.id,
            payload=PaymentPlanCreateRequest(
                name="CLP-30",
                plan_type=PaymentPlanType.CONSTRUCTION_LINKED,
                installments=[
                    InstallmentSpec(milestone="Booking amount", amount_paise=15_00_00_00, due_on=date.today()),
                    InstallmentSpec(milestone="Slab completion", amount_paise=75_00_00_00, due_on=date.today() + timedelta(days=120)),
                    InstallmentSpec(milestone="Possession", amount_paise=60_00_00_00, due_on=date.today() + timedelta(days=365)),
                ],
            ),
        )
        assert len(plan.installments) == 3
        session.refresh(booking)
        assert booking.status == SaleStatus.PAYMENTS_IN_PROGRESS.value

        # First demand: 15% booking amount received.
        receipt1 = service.record_receipt(
            session,
            actor=admin,
            payload=ReceiptCreateRequest(
                installment_id=plan.installments[0].id,
                amount_paise=10_00_00_00,
                channel=ReceiptChannel.UPI,
                reference="UPI-REF-1",
            ),
        )
        assert receipt1.receipt_number.startswith("RCPT-")
        session.refresh(plan.installments[0])
        assert plan.installments[0].status == InstallmentStatus.PART_PAID.value

        # Overpayment is rejected.
        with pytest.raises(ReceiptAmountExceedsOutstandingError):
            service.record_receipt(
                session,
                actor=admin,
                payload=ReceiptCreateRequest(
                    installment_id=plan.installments[0].id,
                    amount_paise=10_00_00_00,  # 5% outstanding, 10% offered
                    channel=ReceiptChannel.CHEQUE,
                ),
            )

        # Close the first installment.
        service.record_receipt(
            session,
            actor=admin,
            payload=ReceiptCreateRequest(
                installment_id=plan.installments[0].id,
                amount_paise=5_00_00_00,
                channel=ReceiptChannel.NEFT,
            ),
        )
        session.refresh(plan.installments[0])
        assert plan.installments[0].status == InstallmentStatus.PAID.value

        ledger = service.ledger(session, actor=admin, booking_id=booking.id)
        assert ledger["collected_paise"] == 15_00_00_00
        assert ledger["outstanding_paise"] == 1_35_00_00_00
        assert any(i["milestone"] == "Booking amount" for i in ledger["installments"])


def test_demand_letter_and_commission_and_plan_amount_validation(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, project, lead = _fixture(session)
        booking = service.create_booking(
            session,
            actor=admin,
            payload=SaleBookingCreateRequest(
                lead_id=lead.id, unit_number="A-101", consideration_paise=10_00_00_00
            ),
        )

        # Plan must sum exactly to consideration.
        with pytest.raises(PaymentPlanAmountMismatchError):
            service.create_plan(
                session,
                actor=admin,
                booking_id=booking.id,
                payload=PaymentPlanCreateRequest(
                    name="Wrong",
                    plan_type=PaymentPlanType.TIME_LINKED,
                    installments=[
                        InstallmentSpec(milestone="Only half", amount_paise=4_00_00_00, due_on=date.today())
                    ],
                ),
            )

        plan = service.create_plan(
            session,
            actor=admin,
            booking_id=booking.id,
            payload=PaymentPlanCreateRequest(
                name="Quarterly",
                plan_type=PaymentPlanType.TIME_LINKED,
                installments=[
                    InstallmentSpec(milestone="Q1", amount_paise=10_00_00_00, due_on=date.today() + timedelta(days=10)),
                ],
            ),
        )

        # P0.3 behavior change: send_demand_letter now PREPARES the letter and
        # opens a pending DEMAND_LETTER approval instead of stamping the sent
        # timestamp immediately; a second admin's decision releases the send.
        updated = service.send_demand_letter(
            session, actor=admin, installment_id=plan.installments[0].id
        )
        letter = updated.__dict__["demand_letter_document"]
        assert letter.review_state == "PENDING_REVIEW"
        assert updated.demand_letter_sent_at is None
        approval = session.query(ApprovalRequest).filter_by(
            reference_id=letter.id, request_type="DEMAND_LETTER"
        ).one()
        assert approval.status == ApprovalStatus.PENDING.value
        assert approval.requested_by_id == admin.id

        from app.modules.auth.security import hash_password as _hash  # noqa: F401

        second_admin = User(
            tenant_id=tenant.id, full_name="Approver",
            email="approver@sales.example",
            password_hash=hash_password(TEST_PASSWORD), role_id=admin.role_id,
            is_active=True,
        )
        session.add(second_admin)
        session.commit()
        from app.modules.approvals import service as approvals_service

        decided = approvals_service.decide(
            session, actor=second_admin, request_id=approval.id, decision="APPROVED"
        )
        assert decided.status == ApprovalStatus.APPROVED.value
        session.refresh(updated)
        assert updated.demand_letter_sent_at is not None
        assert updated.status == InstallmentStatus.DUE.value

        commission = service.create_commission(
            session,
            actor=admin,
            booking_id=booking.id,
            payload=BrokerCommissionCreateRequest(
                broker_name="Realty Partners",
                broker_phone="+919811111111",
                amount_paise=30_00_00_00,  # 2% of ₹10L consideration? -> ₹3,00,000
                basis={"percent": 2},
            ),
        )
        assert commission.status == CommissionStatus.PENDING.value

        paid = service.update_commission(
            session,
            actor=admin,
            commission_id=commission.id,
            status_value=CommissionStatus.PAID,
        )
        assert paid.status == CommissionStatus.PAID.value
        assert paid.paid_at is not None


def test_ledger_closes_booking_when_all_installments_paid(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, project, lead = _fixture(session)
        booking = service.create_booking(
            session,
            actor=admin,
            payload=SaleBookingCreateRequest(
                lead_id=lead.id, unit_number="C-5", consideration_paise=5_00_00_00
            ),
        )
        plan = service.create_plan(
            session,
            actor=admin,
            booking_id=booking.id,
            payload=PaymentPlanCreateRequest(
                name="Full",
                plan_type=PaymentPlanType.CONSTRUCTION_LINKED,
                installments=[
                    InstallmentSpec(milestone="Lump sum", amount_paise=5_00_00_00, due_on=date.today())
                ],
            ),
        )
        service.record_receipt(
            session,
            actor=admin,
            payload=ReceiptCreateRequest(
                installment_id=plan.installments[0].id,
                amount_paise=5_00_00_00,
                channel=ReceiptChannel.LOAN_DISBURSAL,
            ),
        )
        refreshed = session.get(type(booking), booking.id)
        assert refreshed.status == SaleStatus.CLOSED.value


def test_sale_booking_requires_converted_lead(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, project, lead = _fixture(session)
        lead.status = LeadStatus.NEW.value
        session.add(lead)
        session.commit()
        with pytest.raises(HTTPException) as exc:
            service.create_booking(
                session,
                actor=admin,
                payload=SaleBookingCreateRequest(
                    lead_id=lead.id, unit_number="X-1", consideration_paise=100
                ),
            )
        assert exc.value.status_code == 400
