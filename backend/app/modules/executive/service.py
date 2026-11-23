"""Read-only executive aggregation over existing tenant tables.

Every figure in this module is a plain SQL aggregation over tables owned by
other modules; nothing is written and no new tables exist. Each public
function documents its source queries so any number shown to an executive can
be traced back to its tables, filters, and timestamp column.

Dialect note: month bucketing mirrors ``dashboard.repository`` (SQLite uses
``strftime``/``date(..., 'start of month')``; PostgreSQL uses
``date_trunc``). Values are normalized to ``datetime.date`` in Python so both
engines return identical JSON.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import case, cast, func, select
from sqlalchemy.orm import Session

from app.modules.approvals.models import ApprovalRequest, ApprovalStatus
from app.modules.bookings.models import Booking, BookingStatus, VisitSlot
from app.modules.inventory.models import PropertyUnit, UnitStatus
from app.modules.leads.models import Lead, LeadStatus
from app.modules.postsales.models import (
    Installment,
    PaymentPlan,
    Receipt,
    SaleBooking,
    SaleStatus,
)
from app.modules.postsales.repository import (
    OPEN_INSTALLMENT_STATUSES,
    live_receipt_conditions,
)
from app.modules.projects.models import Project
from app.modules.service_desk.models import Ticket, TicketStatus
from app.modules.tenancy.models import Tenant

#: Sale bookings in these statuses are finished outcomes (closed or cancelled)
#: and are excluded from committed-but-unsold inventory value.
NON_UNSOLD_SALE_STATUSES = (SaleStatus.CANCELLED.value, SaleStatus.CLOSED.value)

#: Unit states that no longer count toward unsold sellable inventory.
SOLD_OR_WITHDRAWN_UNIT_STATUSES = (
    UnitStatus.SOLD.value,
    UnitStatus.CANCELLED.value,
    UnitStatus.DRAFT.value,
    UnitStatus.BLOCKED.value,
)

#: Lead lifecycle states that are still in the sales funnel.
ACTIVE_LEAD_STATUSES = (
    LeadStatus.NEW.value,
    LeadStatus.CONTACTED.value,
    LeadStatus.QUALIFIED.value,
    LeadStatus.VISIT_BOOKED.value,
    LeadStatus.VISITED.value,
)

#: Unresolved ticket states for SLA-breach detection (mirrors service_desk:
#: a ticket is breaching while unresolved and past ``sla_due_at``).
OPEN_TICKET_STATUSES = (
    TicketStatus.OPEN.value,
    TicketStatus.IN_PROGRESS.value,
    TicketStatus.WAITING_ON_CUSTOMER.value,
)

#: Ranking weights: bookings dominate, visits confirm, enquiries seed.
VELOCITY_WEIGHT_BOOKINGS = 3.0
VELOCITY_WEIGHT_VISITS = 1.0
VELOCITY_WEIGHT_ENQUIRIES = 0.1

MAX_COCKPIT_MONTHS = 24
DEFAULT_COCKPIT_MONTHS = 12
RANKING_WINDOW_DAYS = 90
OVERDUE_SAMPLE_LIMIT = 10

def _month_bucket(session: Session, column):
    """SQL expression that buckets a timestamp/date column to its month start."""

    dialect = session.get_bind().dialect.name
    if dialect == "sqlite":
        return func.date(column, "start of month")
    return cast(func.date_trunc("month", column), date)


def _as_date(value: Any) -> date:
    """Normalize driver return types (str on SQLite, date/datetime on PG)."""

    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _month_grid(months: int, today: date) -> list[date]:
    """First-of-month dates for the trailing ``months`` window (inclusive)."""

    year, month = today.year, today.month
    firsts: list[date] = []
    for _ in range(months):
        firsts.append(date(year, month, 1))
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
    return list(reversed(firsts))


def _month_start_utc(first: date) -> datetime:
    """UTC midnight bound for DateTime column comparisons (SQLite-safe binds)."""

    return datetime(first.year, first.month, 1, tzinfo=UTC)


def _validate_project(
    session: Session, *, tenant_id: UUID, project_id: UUID | None
) -> Project | None:
    if project_id is None:
        return None
    project = session.scalar(
        select(Project).where(Project.id == project_id, Project.tenant_id == tenant_id)
    )
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found.")
    return project


def _require_tenant(session: Session, tenant_id: UUID) -> Tenant:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found.")
    return tenant


# ---------------------------------------------------------------------------
# Sales velocity
# ---------------------------------------------------------------------------


def sales_velocity(
    session: Session, *, tenant_id: UUID, project_id: UUID | None, months: int
) -> list[dict]:
    """Enquiries → visits → bookings per calendar month.

    Source queries (all tenant-scoped, optionally project-scoped):
      * enquiries      — COUNT(leads) grouped by month of ``leads.created_at``.
      * visits_completed — COUNT(bookings JOIN visit_slots) where
        ``bookings.status = 'COMPLETED'``, grouped by month of
        ``visit_slots.start_time`` (the visit date, not the booking date).
      * bookings / booking_value_paise — COUNT and SUM of
        ``sale_bookings.consideration_paise`` where
        ``sale_bookings.status != 'CANCELLED'``, grouped by month of
        ``sale_bookings.booked_on``.
    """

    today = datetime.now(UTC).date()
    window_start = _month_grid(months, today)[0]
    window_dt = _month_start_utc(window_start)

    def scoped(stmt, column_project):
        if project_id is not None:
            stmt = stmt.where(column_project == project_id)
        return stmt

    lead_rows = session.execute(
        scoped(
            select(
                _month_bucket(session, Lead.created_at).label("m"),
                func.count(Lead.id),
            )
            .where(Lead.tenant_id == tenant_id, Lead.created_at >= window_dt)
            .group_by(_month_bucket(session, Lead.created_at)),
            Lead.project_id,
        )
    ).all()
    visit_rows = session.execute(
        scoped(
            select(
                _month_bucket(session, VisitSlot.start_time).label("m"),
                func.count(Booking.id),
            )
            .join(VisitSlot, Booking.slot_id == VisitSlot.id)
            .where(
                Booking.tenant_id == tenant_id,
                Booking.status == BookingStatus.COMPLETED.value,
                VisitSlot.start_time >= window_dt,
            )
            .group_by(_month_bucket(session, VisitSlot.start_time)),
            Booking.project_id,
        )
    ).all()
    booking_rows = session.execute(
        scoped(
            select(
                _month_bucket(session, SaleBooking.booked_on).label("m"),
                func.count(SaleBooking.id),
                func.coalesce(func.sum(SaleBooking.consideration_paise), 0),
            )
            .where(
                SaleBooking.tenant_id == tenant_id,
                SaleBooking.status != "CANCELLED",
                SaleBooking.booked_on >= window_start,
            )
            .group_by(_month_bucket(session, SaleBooking.booked_on)),
            SaleBooking.project_id,
        )
    ).all()

    enquiries = {_as_date(r[0]): int(r[1]) for r in lead_rows}
    visits = {_as_date(r[0]): int(r[1]) for r in visit_rows}
    bookings = {_as_date(r[0]): int(r[1]) for r in booking_rows}
    value = {_as_date(r[0]): int(r[2]) for r in booking_rows}

    return [
        {
            "month": month,
            "enquiries": enquiries.get(month, 0),
            "visits_completed": visits.get(month, 0),
            "bookings": bookings.get(month, 0),
            "booking_value_paise": value.get(month, 0),
        }
        for month in _month_grid(months, today)
    ]


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


def collections_by_month(
    session: Session, *, tenant_id: UUID, project_id: UUID | None, months: int
) -> list[dict]:
    """collected_paise from live receipts grouped by month of ``receipts.paid_at``.

    Source query: SUM(receipts.amount_paise) and COUNT(receipts.id) joined
    through installments → payment_plans → sale_bookings so a project filter
    applies to the booking's project. ``receipts.voided_at IS NULL`` (via
    ``postsales.repository.live_receipt_conditions``) keeps voided receipts out
    of the total while leaving the audit rows untouched.
    """

    today = datetime.now(UTC).date()
    window_start = _month_grid(months, today)[0]
    window_dt = _month_start_utc(window_start)
    bucket = _month_bucket(session, Receipt.paid_at)

    stmt = (
        select(bucket.label("m"), func.count(Receipt.id), func.coalesce(func.sum(Receipt.amount_paise), 0))
        .join(Installment, Receipt.installment_id == Installment.id)
        .join(PaymentPlan, Installment.plan_id == PaymentPlan.id)
        .join(SaleBooking, PaymentPlan.sale_booking_id == SaleBooking.id)
        .where(
            Receipt.tenant_id == tenant_id,
            *live_receipt_conditions(),
            Receipt.paid_at >= window_dt,
        )
        .group_by(bucket)
    )
    if project_id is not None:
        stmt = stmt.where(SaleBooking.project_id == project_id)
    rows = session.execute(stmt).all()

    totals = {_as_date(r[0]): (int(r[1]), int(r[2])) for r in rows}
    return [
        {
            "month": month,
            "collected_paise": totals.get(month, (0, 0))[1],
            "receipt_count": totals.get(month, (0, 0))[0],
        }
        for month in _month_grid(months, today)
    ]


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------


def inventory_summary(
    session: Session, *, tenant_id: UUID, project_id: UUID | None
) -> dict:
    """Availability counts plus unsold value taken from booking consideration.

    Source queries:
      * availability — COUNT(property_units) grouped by ``property_units.status``
        (the same shape as ``inventory.service.availability_summary``), scoped
        to one project or all tenant projects.
      * unsold_value_paise — SUM(sale_bookings.consideration_paise) where
        ``sale_bookings.status NOT IN ('CANCELLED','CLOSED')``: money committed
        on inventory that has not reached a terminal sold/cancelled outcome.
    """

    unit_stmt = (
        select(PropertyUnit.status, func.count(PropertyUnit.id))
        .where(PropertyUnit.tenant_id == tenant_id)
        .group_by(PropertyUnit.status)
    )
    booking_stmt = select(
        func.coalesce(func.sum(SaleBooking.consideration_paise), 0),
    ).where(
        SaleBooking.tenant_id == tenant_id,
        SaleBooking.status.notin_(NON_UNSOLD_SALE_STATUSES),
    )
    if project_id is not None:
        unit_stmt = unit_stmt.where(PropertyUnit.project_id == project_id)
        booking_stmt = booking_stmt.where(SaleBooking.project_id == project_id)

    counts_by_status = {row[0]: int(row[1]) for row in session.execute(unit_stmt).all()}
    unsold_value = int(session.execute(booking_stmt).scalar() or 0)

    return {
        "project_id": project_id,
        "total_units": sum(counts_by_status.values()),
        "counts_by_status": counts_by_status,
        "available": counts_by_status.get(UnitStatus.AVAILABLE.value, 0),
        "on_hold": counts_by_status.get(UnitStatus.ON_HOLD.value, 0),
        "reserved": counts_by_status.get(UnitStatus.RESERVED.value, 0),
        "booked": counts_by_status.get(UnitStatus.BOOKED.value, 0),
        "sold": counts_by_status.get(UnitStatus.SOLD.value, 0),
        "unsold_value_paise": unsold_value,
    }


# ---------------------------------------------------------------------------
# Approvals / overdue installments / tickets
# ---------------------------------------------------------------------------


def approvals_summary(
    session: Session, *, tenant_id: UUID, project_id: UUID | None
) -> dict:
    """Pending approval workload.

    Source query: COUNT and SUM(amount_paise) on ``approval_requests`` with
    ``status = 'PENDING'``. ``project_id`` cannot scope an approval generically
    (references span many entities), so approvals stay tenant-wide; the
    breakdown is by ``request_type``.
    """

    rows = session.execute(
        select(
            ApprovalRequest.request_type,
            func.count(ApprovalRequest.id),
            func.coalesce(func.sum(ApprovalRequest.amount_paise), 0),
        )
        .where(
            ApprovalRequest.tenant_id == tenant_id,
            ApprovalRequest.status == ApprovalStatus.PENDING.value,
        )
        .group_by(ApprovalRequest.request_type)
    ).all()

    by_type = {row[0]: int(row[1]) for row in rows}
    return {
        "pending_count": sum(by_type.values()),
        "pending_amount_paise": sum(int(r[2]) for r in rows),
        "by_type": by_type,
    }


def _overdue_conditions(as_of: date):
    """Installments still open (per postsales OPEN_INSTALLMENT_STATUSES) whose
    ``due_on`` has passed. Status is *not* assumed to have been refreshed to
    OVERDUE yet, so PENDING/DUE rows past due count here too."""

    return (
        Installment.status.in_(OPEN_INSTALLMENT_STATUSES),
        Installment.due_on < as_of,
    )


def _paid_paise_per_installment(session: Session, tenant_id: UUID):
    """Subquery: live (non-voided) receipt total per installment."""

    return (
        select(
            Receipt.installment_id.label("installment_id"),
            func.coalesce(func.sum(Receipt.amount_paise), 0).label("paid_paise"),
        )
        .where(Receipt.tenant_id == tenant_id, *live_receipt_conditions())
        .group_by(Receipt.installment_id)
        .subquery()
    )


def overdue_installments(
    session: Session, *, tenant_id: UUID, project_id: UUID | None, as_of: date | None = None
) -> dict:
    """Overdue collection exposure.

    Source query: ``installments`` LEFT JOIN live-receipt totals, joined through
    ``payment_plans`` → ``sale_bookings`` for project scoping. An installment is
    overdue when its status is still open (PENDING/DUE/PART_PAID/OVERDUE, per
    ``postsales.repository.OPEN_INSTALLMENT_STATUSES``) and ``due_on`` is before
    the as-of date. ``outstanding_paise`` = amount_paise − live receipts paid,
    floored at zero (PART_PAID rows net down; voided receipts never offset).
    """

    today = as_of or datetime.now(UTC).date()
    paid = _paid_paise_per_installment(session, tenant_id)
    unpaid = Installment.amount_paise - func.coalesce(paid.c.paid_paise, 0)
    outstanding = case((unpaid > 0, unpaid), else_=0).label("outstanding_paise")

    stmt = (
        select(
            func.count(Installment.id),
            func.coalesce(func.sum(outstanding), 0),
            func.min(Installment.due_on),
        )
        .select_from(Installment)
        .join(PaymentPlan, Installment.plan_id == PaymentPlan.id)
        .join(SaleBooking, PaymentPlan.sale_booking_id == SaleBooking.id)
        .outerjoin(paid, paid.c.installment_id == Installment.id)
        .where(Installment.tenant_id == tenant_id, *_overdue_conditions(today))
    )
    if project_id is not None:
        stmt = stmt.where(SaleBooking.project_id == project_id)
    count, amount, oldest = session.execute(stmt).one()

    sample_stmt = (
        select(
            Installment.id,
            SaleBooking.unit_number,
            Installment.milestone,
            Installment.amount_paise,
            Installment.due_on,
            func.coalesce(paid.c.paid_paise, 0),
        )
        .select_from(Installment)
        .join(PaymentPlan, Installment.plan_id == PaymentPlan.id)
        .join(SaleBooking, PaymentPlan.sale_booking_id == SaleBooking.id)
        .outerjoin(paid, paid.c.installment_id == Installment.id)
        .where(Installment.tenant_id == tenant_id, *_overdue_conditions(today))
        .order_by(Installment.due_on.asc(), Installment.id.asc())
        .limit(OVERDUE_SAMPLE_LIMIT)
    )
    if project_id is not None:
        sample_stmt = sample_stmt.where(SaleBooking.project_id == project_id)

    sample = [
        {
            "installment_id": row[0],
            "unit_number": row[1],
            "milestone": row[2],
            "amount_paise": int(row[3]) - int(row[5]) if int(row[3]) > int(row[5]) else 0,
            "due_on": _as_date(row[4]),
            "days_overdue": max((today - _as_date(row[4])).days, 0),
        }
        for row in session.execute(sample_stmt).all()
    ]

    return {
        "count": int(count or 0),
        "amount_paise": int(amount or 0),
        "oldest_due_on": _as_date(oldest) if oldest is not None else None,
        "sample": sample,
    }


def ticket_sla_summary(session: Session, *, tenant_id: UUID) -> dict:
    """Service-desk SLA breaches.

    Source query: COUNT on ``tickets`` where status is unresolved (OPEN /
    IN_PROGRESS / WAITING_ON_CUSTOMER) grouped by ``priority``; the breach
    subset additionally requires ``sla_due_at < now`` — the same definition the
    service-desk queue uses for its ``breach_only`` filter.
    """

    now = datetime.now(UTC)
    rows = session.execute(
        select(Ticket.priority, func.count(Ticket.id))
        .where(Ticket.tenant_id == tenant_id, Ticket.status.in_(OPEN_TICKET_STATUSES))
        .group_by(Ticket.priority)
    ).all()
    breach_rows = session.execute(
        select(Ticket.priority, func.count(Ticket.id))
        .where(
            Ticket.tenant_id == tenant_id,
            Ticket.status.in_(OPEN_TICKET_STATUSES),
            Ticket.sla_due_at < now,
        )
        .group_by(Ticket.priority)
    ).all()

    open_by_priority = {row[0]: int(row[1]) for row in rows}
    breaching = {row[0]: int(row[1]) for row in breach_rows}
    return {
        "breaching_count": sum(breaching.values()),
        "open_count": sum(open_by_priority.values()),
        "by_priority": breaching,
    }


# ---------------------------------------------------------------------------
# Project ranking
# ---------------------------------------------------------------------------


def project_ranking(
    session: Session, *, tenant_id: UUID, window_days: int = RANKING_WINDOW_DAYS
) -> list[dict]:
    """Projects ranked by trailing-window sales velocity.

    Source queries over the last ``window_days`` days (UTC):
      * enquiries — COUNT(leads.created_at in window) per project.
      * visits_completed — COMPLETED bookings by ``visit_slots.start_time``.
      * bookings / booking_value_paise — non-cancelled sale_bookings by
        ``booked_on``.
      * collected_paise — live receipts joined to sale_bookings by ``paid_at``.
      * unsold_units — saleable ``property_units`` not SOLD/CANCELLED/DRAFT/BLOCKED.
    ``velocity_score = bookings*3 + visits_completed*1 + enquiries*0.1`` —
    deterministic weighting so ties break on ``project_name``.
    """

    since = datetime.now(UTC) - timedelta(days=window_days)
    projects = session.scalars(
        select(Project).where(Project.tenant_id == tenant_id).order_by(Project.name)
    ).all()

    def per_project(rows) -> dict[UUID, tuple[int, ...]]:
        return {row[0]: tuple(int(v or 0) for v in row[1:]) for row in rows}

    enquiries = per_project(
        session.execute(
            select(Lead.project_id, func.count(Lead.id))
            .where(Lead.tenant_id == tenant_id, Lead.created_at >= since)
            .group_by(Lead.project_id)
        ).all()
    )
    visits = per_project(
        session.execute(
            select(Booking.project_id, func.count(Booking.id))
            .join(VisitSlot, Booking.slot_id == VisitSlot.id)
            .where(
                Booking.tenant_id == tenant_id,
                Booking.status == BookingStatus.COMPLETED.value,
                VisitSlot.start_time >= since,
            )
            .group_by(Booking.project_id)
        ).all()
    )
    booking_rows = session.execute(
        select(
            SaleBooking.project_id,
            func.count(SaleBooking.id),
            func.coalesce(func.sum(SaleBooking.consideration_paise), 0),
        )
        .where(
            SaleBooking.tenant_id == tenant_id,
            SaleBooking.status != "CANCELLED",
            SaleBooking.booked_on >= since.date(),
        )
        .group_by(SaleBooking.project_id)
    ).all()
    bookings = per_project(booking_rows)
    collected = per_project(
        session.execute(
            select(SaleBooking.project_id, func.coalesce(func.sum(Receipt.amount_paise), 0))
            .join(PaymentPlan, PaymentPlan.sale_booking_id == SaleBooking.id)
            .join(Installment, Installment.plan_id == PaymentPlan.id)
            .join(Receipt, Receipt.installment_id == Installment.id)
            .where(
                Receipt.tenant_id == tenant_id,
                *live_receipt_conditions(),
                Receipt.paid_at >= since,
            )
            .group_by(SaleBooking.project_id)
        ).all()
    )
    unsold = per_project(
        session.execute(
            select(PropertyUnit.project_id, func.count(PropertyUnit.id))
            .where(
                PropertyUnit.tenant_id == tenant_id,
                PropertyUnit.saleable.is_(True),
                PropertyUnit.status.notin_(SOLD_OR_WITHDRAWN_UNIT_STATUSES),
            )
            .group_by(PropertyUnit.project_id)
        ).all()
    )

    ranking: list[dict] = []
    for project in projects:
        lead_count = enquiries.get(project.id, (0,))[0]
        visit_count = visits.get(project.id, (0,))[0]
        booking_count, booking_value = bookings.get(project.id, (0, 0))
        collected_paise = collected.get(project.id, (0,))[0]
        unsold_units = unsold.get(project.id, (0,))[0]
        score = (
            booking_count * VELOCITY_WEIGHT_BOOKINGS
            + visit_count * VELOCITY_WEIGHT_VISITS
            + lead_count * VELOCITY_WEIGHT_ENQUIRIES
        )
        ranking.append(
            {
                "project_id": project.id,
                "project_name": project.name,
                "enquiries": lead_count,
                "visits_completed": visit_count,
                "bookings": booking_count,
                "booking_value_paise": booking_value,
                "collected_paise": collected_paise,
                "unsold_units": unsold_units,
                "velocity_score": round(score, 4),
            }
        )

    ranking.sort(key=lambda row: (-row["velocity_score"], row["project_name"]))
    return ranking


# ---------------------------------------------------------------------------
# Cockpit assembly
# ---------------------------------------------------------------------------


def cockpit(
    session: Session,
    *,
    tenant_id: UUID,
    project_id: UUID | None = None,
    months: int = DEFAULT_COCKPIT_MONTHS,
) -> dict:
    """Assemble the full executive cockpit payload (read-only).

    Combines :func:`sales_velocity`, :func:`collections_by_month`,
    :func:`inventory_summary`, :func:`approvals_summary`,
    :func:`overdue_installments`, :func:`ticket_sla_summary`, and
    :func:`project_ranking`; each section's docstring names its source tables
    and filters. ``months`` is clamped to 1..24.
    """

    _require_tenant(session, tenant_id)
    _validate_project(session, tenant_id=tenant_id, project_id=project_id)
    months = min(max(months, 1), MAX_COCKPIT_MONTHS)

    return {
        "generated_at": datetime.now(UTC),
        "tenant_id": tenant_id,
        "project_id": project_id,
        "window_months": months,
        "sales_velocity": sales_velocity(
            session, tenant_id=tenant_id, project_id=project_id, months=months
        ),
        "collections": collections_by_month(
            session, tenant_id=tenant_id, project_id=project_id, months=months
        ),
        "inventory": inventory_summary(
            session, tenant_id=tenant_id, project_id=project_id
        ),
        "approvals": approvals_summary(session, tenant_id=tenant_id, project_id=project_id),
        "overdue_installments": overdue_installments(
            session, tenant_id=tenant_id, project_id=project_id
        ),
        "ticket_sla": ticket_sla_summary(session, tenant_id=tenant_id),
        "project_ranking": project_ranking(session, tenant_id=tenant_id),
    }
