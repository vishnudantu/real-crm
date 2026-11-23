"""Executive cockpit tests: deterministic aggregation math on seeded fixtures.

Known leads/visits/sale bookings/receipts/tickets/approvals produce exact
per-month numbers; voided receipts are excluded; overdue installments net down
by live receipts; admin gating and briefing determinism are covered here.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.approvals.models import ApprovalRequest, ApprovalStatus
from app.modules.auth.security import hash_password
from app.modules.bookings.models import Booking, BookingStatus, VisitSlot
import app.modules.executive.briefing as briefing_service
from app.modules.executive import service
from app.modules.inventory.models import PropertyUnit, UnitStatus
from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.postsales.models import (
    Installment,
    InstallmentStatus,
    PaymentPlan,
    Receipt,
    ReceiptChannel,
    SaleBooking,
    SaleStatus,
)
from app.modules.projects.models import Project, ProjectStatus
from app.modules.service_desk.models import Ticket, TicketPriority, TicketStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD


def _utc(year: int, month: int, day: int, hour: int = 9) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC)


def _fixture(session: Session) -> tuple[Tenant, User, Project]:
    tenant = Tenant(slug=f"exec-{uuid4().hex[:8]}", name="Exec Co")
    session.add(tenant)
    # Reuse an existing ADMIN role when present (a session may seed several fixtures).
    role = session.scalar(select(Role).where(Role.name == RoleName.ADMIN.value))
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
    session.flush()
    admin = User(
        tenant_id=tenant.id,
        full_name="Exec Admin",
        email=f"admin-{uuid4().hex[:8]}@exec.example",
        password_hash=hash_password(TEST_PASSWORD),
        role_id=role.id,
        is_active=True,
    )
    session.add(admin)
    session.flush()  # assign admin.id before the project's created_by FK
    project = Project(
        tenant_id=tenant.id,
        name="Skyline Towers",
        slug=f"sky-{uuid4().hex[:8]}",
        location="Pune",
        status=ProjectStatus.ACTIVE.value,
        created_by=admin.id,
    )
    session.add(project)
    session.flush()
    return tenant, admin, project


def _lead(
    session: Session, tenant: Tenant, project: Project, *, created_at: datetime,
    status: LeadStatus = LeadStatus.NEW,
) -> Lead:
    lead = Lead(
        tenant_id=tenant.id,
        full_name=f"Buyer {uuid4().hex[:6]}",
        email=f"b-{uuid4().hex[:8]}@exec.example",
        project_id=project.id,
        source=LeadSource.WEBSITE.value,
        status=status.value,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(lead)
    session.flush()
    return lead


def _completed_visit(
    session: Session, tenant: Tenant, project: Project, admin: User, lead: Lead,
    *, slot_time: datetime,
) -> None:
    slot = VisitSlot(
        tenant_id=tenant.id, project_id=project.id,
        start_time=slot_time, end_time=slot_time + timedelta(hours=1),
    )
    session.add(slot)
    session.flush()
    session.add(
        Booking(
            tenant_id=tenant.id, slot_id=slot.id, lead_id=lead.id,
            project_id=project.id, buyer_id=admin.id,
            status=BookingStatus.COMPLETED.value,
            created_at=slot_time - timedelta(days=1),
        )
    )
    session.flush()


def _sale_booking(
    session: Session, tenant: Tenant, project: Project, lead: Lead, *,
    unit_number: str, consideration_paise: int, booked_on: date,
    status: SaleStatus = SaleStatus.BOOKED,
    installments: list[tuple[str, int, date, InstallmentStatus]] | None = None,
) -> SaleBooking:
    booking = SaleBooking(
        tenant_id=tenant.id, lead_id=lead.id, project_id=project.id,
        unit_number=unit_number, consideration_paise=consideration_paise,
        status=status.value, booked_on=booked_on,
    )
    session.add(booking)
    session.flush()
    if installments:
        plan = PaymentPlan(
            tenant_id=tenant.id, sale_booking_id=booking.id, name="Standard",
            plan_type="TIME_LINKED",
        )
        session.add(plan)
        session.flush()
        for seq, (milestone, amount, due_on, inst_status) in enumerate(installments, start=1):
            session.add(
                Installment(
                    tenant_id=tenant.id, plan_id=plan.id, sequence_no=seq,
                    milestone=milestone, amount_paise=amount, due_on=due_on,
                    status=inst_status.value,
                )
            )
        session.flush()
    return booking


def _receipt(
    session: Session, tenant: Tenant, installment: Installment, *,
    amount_paise: int, paid_at: datetime, voided: bool = False,
) -> Receipt:
    receipt = Receipt(
        tenant_id=tenant.id, installment_id=installment.id,
        receipt_number=f"RCP-{uuid4().hex[:10]}", amount_paise=amount_paise,
        channel=ReceiptChannel.UPI.value, paid_at=paid_at,
        voided_at=_utc(2026, 11, 1) if voided else None,
        void_reason="duplicate entry" if voided else None,
    )
    session.add(receipt)
    session.flush()
    return receipt


def _plan_installments(session: Session, booking: SaleBooking) -> list[Installment]:
    return list(
        session.scalars(
            select(Installment)
            .join(PaymentPlan, Installment.plan_id == PaymentPlan.id)
            .where(PaymentPlan.sale_booking_id == booking.id)
            .order_by(Installment.sequence_no)
        )
    )


def _months() -> tuple[date, date]:
    """(first of this month, first of previous month) in UTC."""

    today = datetime.now(UTC).date()
    this_first = date(today.year, today.month, 1)
    prev_end = this_first - timedelta(days=1)
    return this_first, date(prev_end.year, prev_end.month, 1)


def _day_in_month(first: date, session: Session) -> int:
    """A day-of-month valid for the given month (clamped for tiny fixtures)."""

    return min(datetime.now(UTC).day if first.month == datetime.now(UTC).month else 14, 28)


# ---------------------------------------------------------------------------
# Aggregation math
# ---------------------------------------------------------------------------


def test_cockpit_sales_velocity_and_collections_math(
    test_session_factory: sessionmaker[Session],
) -> None:
    this_first, prev_first = _months()

    with test_session_factory() as session:
        tenant, admin, project = _fixture(session)
        d_prev = _day_in_month(prev_first, session)
        d_this = _day_in_month(this_first, session)

        lead_p1 = _lead(session, tenant, project, created_at=_utc(prev_first.year, prev_first.month, d_prev))
        _lead(session, tenant, project, created_at=_utc(prev_first.year, prev_first.month, 20))
        lead_now = _lead(session, tenant, project, created_at=_utc(this_first.year, this_first.month, d_this))

        _completed_visit(session, tenant, project, admin, lead_p1, slot_time=_utc(prev_first.year, prev_first.month, 7))
        _completed_visit(session, tenant, project, admin, lead_now, slot_time=_utc(this_first.year, this_first.month, d_this, 10))
        _completed_visit(session, tenant, project, admin, lead_now, slot_time=_utc(this_first.year, this_first.month, d_this, 11))

        b1 = _sale_booking(
            session, tenant, project, lead_p1, unit_number="A-101",
            consideration_paise=1_50_00_00_00, booked_on=prev_first,
            installments=[("Booking", 30_00_00_00, this_first + timedelta(days=2), InstallmentStatus.PENDING)],
        )
        lead_b2 = _lead(session, tenant, project, created_at=_utc(prev_first.year, prev_first.month, 6))
        b2 = _sale_booking(
            session, tenant, project, lead_b2, unit_number="A-102",
            consideration_paise=2_00_00_00_00, booked_on=this_first,
            installments=[("Booking", 40_00_00_00, this_first + timedelta(days=2), InstallmentStatus.PENDING)],
        )
        lead_b3 = _lead(session, tenant, project, created_at=_utc(prev_first.year, prev_first.month, 8))
        _sale_booking(
            session, tenant, project, lead_b3, unit_number="A-103",
            consideration_paise=50_00_00_00, booked_on=this_first, status=SaleStatus.CANCELLED,
        )

        inst_b2 = _plan_installments(session, b2)[0]
        _receipt(session, tenant, inst_b2, amount_paise=20_00_00_00, paid_at=_utc(this_first.year, this_first.month, d_this, 12))
        _receipt(session, tenant, inst_b2, amount_paise=5_00_00_00, paid_at=_utc(this_first.year, this_first.month, d_this, 13), voided=True)
        session.commit()

        payload = service.cockpit(session, tenant_id=tenant.id, project_id=None, months=3)

        by_month = {point["month"]: point for point in payload["sales_velocity"]}
        assert by_month[prev_first]["enquiries"] == 4  # p1, day-20, b2, b3 leads
        assert by_month[prev_first]["visits_completed"] == 1
        assert by_month[prev_first]["bookings"] == 1
        assert by_month[prev_first]["booking_value_paise"] == 1_50_00_00_00
        assert by_month[this_first]["enquiries"] == 1
        assert by_month[this_first]["visits_completed"] == 2
        assert by_month[this_first]["bookings"] == 1  # CANCELLED booking excluded
        assert by_month[this_first]["booking_value_paise"] == 2_00_00_00_00

        collections = {point["month"]: point for point in payload["collections"]}
        assert collections[this_first]["collected_paise"] == 20_00_00_00
        assert collections[this_first]["receipt_count"] == 1
        assert payload["window_months"] == 3
        assert len(payload["sales_velocity"]) == 3


def test_cockpit_inventory_approvals_overdue_sla_and_ranking(
    test_session_factory: sessionmaker[Session],
) -> None:
    today = datetime.now(UTC).date()
    this_first, _prev = _months()

    with test_session_factory() as session:
        tenant, _admin, project = _fixture(session)

        session.add_all(
            [
                PropertyUnit(tenant_id=tenant.id, project_id=project.id, internal_code="U-AV", status=UnitStatus.AVAILABLE.value),
                PropertyUnit(tenant_id=tenant.id, project_id=project.id, internal_code="U-AV2", status=UnitStatus.AVAILABLE.value),
                PropertyUnit(tenant_id=tenant.id, project_id=project.id, internal_code="U-BK", status=UnitStatus.BOOKED.value),
                PropertyUnit(tenant_id=tenant.id, project_id=project.id, internal_code="U-SOLD", status=UnitStatus.SOLD.value),
                PropertyUnit(tenant_id=tenant.id, project_id=project.id, internal_code="U-DRAFT", status=UnitStatus.DRAFT.value),
            ]
        )

        lead = _lead(session, tenant, project, created_at=_utc(this_first.year, this_first.month, 3))
        # One CANCELLED sale booking must not inflate unsold value.
        lead_x = _lead(session, tenant, project, created_at=_utc(this_first.year, this_first.month, 4))
        _sale_booking(
            session, tenant, project, lead_x, unit_number="U-X",
            consideration_paise=99_00_00_00, booked_on=this_first, status=SaleStatus.CANCELLED,
        )
        booking = _sale_booking(
            session, tenant, project, lead, unit_number="U-BK",
            consideration_paise=1_20_00_00_00, booked_on=this_first,
            installments=[
                ("Slab", 30_00_00_00, today - timedelta(days=10), InstallmentStatus.DUE),
                ("Possession", 40_00_00_00, today - timedelta(days=5), InstallmentStatus.OVERDUE),
                ("Booking", 20_00_00_00, today + timedelta(days=20), InstallmentStatus.PAID),
            ],
        )
        insts = _plan_installments(session, booking)
        _receipt(session, tenant, insts[0], amount_paise=10_00_00_00, paid_at=_utc(today.year, today.month, 2))
        _receipt(session, tenant, insts[1], amount_paise=40_00_00_00, paid_at=_utc(today.year, today.month, 2), voided=True)
        _receipt(session, tenant, insts[2], amount_paise=20_00_00_00, paid_at=_utc(today.year, today.month, 2))

        session.add_all(
            [
                ApprovalRequest(
                    tenant_id=tenant.id, request_type="DISCOUNT", reference_type="UNIT",
                    reference_id=uuid4(), reason="festive offer", amount_paise=500_00,
                    status=ApprovalStatus.PENDING.value,
                ),
                ApprovalRequest(
                    tenant_id=tenant.id, request_type="CAR_REQUEST", reference_type="BOOKING",
                    reference_id=uuid4(), reason="chauffeur", amount_paise=2_00_000,
                    status=ApprovalStatus.PENDING.value,
                ),
                ApprovalRequest(
                    tenant_id=tenant.id, request_type="DISCOUNT", reference_type="UNIT",
                    reference_id=uuid4(), reason="already decided",
                    status=ApprovalStatus.APPROVED.value,
                    decided_at=_utc(today.year, today.month, 2),
                ),
            ]
        )

        session.add_all(
            [
                Ticket(
                    tenant_id=tenant.id, ticket_number=f"TCK-{uuid4().hex[:6]}",
                    subject="Payment issue", description="x",
                    priority=TicketPriority.URGENT.value, status=TicketStatus.IN_PROGRESS.value,
                    sla_due_at=datetime.now(UTC) - timedelta(hours=2),
                ),
                Ticket(
                    tenant_id=tenant.id, ticket_number=f"TCK-{uuid4().hex[:6]}",
                    subject="Doc request", description="x",
                    priority=TicketPriority.LOW.value, status=TicketStatus.OPEN.value,
                    sla_due_at=datetime.now(UTC) + timedelta(days=2),
                ),
                Ticket(
                    tenant_id=tenant.id, ticket_number=f"TCK-{uuid4().hex[:6]}",
                    subject="Resolved late", description="x",
                    priority=TicketPriority.HIGH.value, status=TicketStatus.RESOLVED.value,
                    sla_due_at=datetime.now(UTC) - timedelta(hours=5),
                ),
            ]
        )
        session.commit()

        payload = service.cockpit(session, tenant_id=tenant.id, project_id=None, months=2)

        inv = payload["inventory"]
        assert inv["total_units"] == 5
        assert inv["available"] == 2
        assert inv["booked"] == 1
        assert inv["sold"] == 1
        assert inv["unsold_value_paise"] == 1_20_00_00_00  # CANCELLED booking excluded

        assert payload["approvals"]["pending_count"] == 2
        assert payload["approvals"]["pending_amount_paise"] == 2_50_000
        assert payload["approvals"]["by_type"] == {"CAR_REQUEST": 1, "DISCOUNT": 1}

        overdue = payload["overdue_installments"]
        assert overdue["count"] == 2
        # (30L − 10L live) + (40L − voided) = 60L outstanding.
        assert overdue["amount_paise"] == 60_00_00_00
        assert overdue["oldest_due_on"] == today - timedelta(days=10)
        assert [row["amount_paise"] for row in overdue["sample"]] == [20_00_00_00, 40_00_00_00]
        assert overdue["sample"][0]["days_overdue"] == 10

        sla = payload["ticket_sla"]
        assert sla["open_count"] == 2
        assert sla["breaching_count"] == 1  # RESOLVED late ticket excluded
        assert sla["by_priority"] == {"URGENT": 1}

        ranking = payload["project_ranking"]
        assert len(ranking) == 1
        row = ranking[0]
        assert row["bookings"] == 1
        # 1 booking × 3 + 0 visits × 1 + 2 leads × 0.1
        assert row["velocity_score"] == pytest.approx(3.2)
        assert row["unsold_units"] == 3  # AVAILABLE ×2 + BOOKED (SOLD/DRAFT out)


def test_cockpit_tenant_isolation_and_project_validation(
    test_session_factory: sessionmaker[Session],
) -> None:
    this_first, _prev = _months()
    with test_session_factory() as session:
        tenant_a, _admin_a, _project_a = _fixture(session)
        tenant_b, _admin_b, project_b = _fixture(session)
        _lead(session, tenant_b, project_b, created_at=_utc(this_first.year, this_first.month, 5))
        session.commit()

        payload = service.cockpit(session, tenant_id=tenant_a.id, project_id=None, months=2)
        assert all(point["enquiries"] == 0 for point in payload["sales_velocity"])
        assert payload["inventory"]["total_units"] == 0

        with pytest.raises(HTTPException) as exc:
            service.cockpit(session, tenant_id=tenant_a.id, project_id=project_b.id)
        assert exc.value.status_code == 404


def test_format_paise_indian_boundaries() -> None:
    assert briefing_service.format_paise_indian(0) == "₹0"
    assert briefing_service.format_paise_indian(99_99) == "₹99"  # 9999 paise = ₹99.99, truncated to whole rupees
    assert briefing_service.format_paise_indian(10_000_000) == "₹1.00 L"      # 1e7 paise = 1 lakh
    assert briefing_service.format_paise_indian(123_456_700) == "₹12.35 L"    # ₹12,34,567 = 12.35 lakh
    assert briefing_service.format_paise_indian(1_000_000_000) == "₹1.00 Cr"  # 1e9 paise = 1 crore
