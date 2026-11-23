"""Deterministic morning briefing: factual SQL counts + fixed template lines.

Read-only over existing tenant tables. No LLM/AI call anywhere — re-rendering
the same UTC day against unchanged data always produces identical lines. Each
source query is documented inline so every figure is traceable to its table,
filter, and timestamp column. Aggregation helpers shared with the cockpit
(``overdue_installments``, ``ticket_sla_summary``, ``_require_tenant``) are
imported from :mod:`app.modules.executive.service`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.modules.approvals.models import ApprovalRequest, ApprovalStatus
from app.modules.bookings.models import Booking, BookingStatus, VisitSlot
from app.modules.leads.models import Lead, LeadAssignment
from app.modules.postsales.models import Receipt, SaleBooking, SaleStatus
from app.modules.postsales.repository import live_receipt_conditions
from app.modules.service_desk.models import Ticket
from app.modules.executive.service import (
    ACTIVE_LEAD_STATUSES,
    NON_UNSOLD_SALE_STATUSES,
    _require_tenant,
    overdue_installments,
    ticket_sla_summary,
)

# Indian minor-unit thresholds (1 rupee = 100 paise):
#   1 lakh  = ₹1,00,000   = 1e5 rupees = 1e7 paise
#   1 crore = ₹1,00,00,000 = 1e7 rupees = 1e9 paise
_CRORE_PAISE = 1_000_000_000  # 1 crore in paise
_LAKH_PAISE = 10_000_000      # 1 lakh in paise


def format_paise_indian(paise: int) -> str:
    """Render an integer paise amount as a compact deterministic INR string.

    ≥1 Cr → '₹X.XX Cr', ≥1 L → '₹X.XX L', else whole rupees with thousands
    grouping. Pure arithmetic on integers; no locale library, so the output is
    identical on every platform (required for briefing determinism).
    """

    if paise >= _CRORE_PAISE:
        return f"₹{paise / _CRORE_PAISE:.2f} Cr"
    if paise >= _LAKH_PAISE:
        return f"₹{paise / _LAKH_PAISE:.2f} L"
    return f"₹{paise // 100:,}"


def _day_window(day: date) -> tuple[datetime, datetime]:
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    return start, start + timedelta(days=1)


def briefing(
    session: Session, *, tenant_id: UUID, briefing_date: date | None = None
) -> dict:
    """Deterministic factual digest for one UTC calendar day (default: yesterday).

    Source queries, all tenant-scoped against the day window
    ``[day 00:00 UTC, day+1 00:00 UTC)``:
      * leads — COUNT on ``leads.created_at`` in the window.
      * visits_completed — COMPLETED ``bookings`` whose ``visit_slots.start_time``
        falls in the window.
      * visit_bookings_created / cancelled — ``bookings.created_at`` /
        ``bookings.cancelled_at`` in the window.
      * sale_bookings / value — non-cancelled ``sale_bookings.booked_on = day``.
      * receipts / paise — live receipts (``voided_at IS NULL``) by ``paid_at``.
      * tickets created / resolved — ``tickets.created_at`` / ``resolved_at``.
      * approvals decided — ``approval_requests.decided_at``.
      * open items — pending approvals, SLA-breaching open tickets, overdue
        installments (due_on < day+1), unassigned active leads, and active
        (non-terminal) sale bookings.
    ``lines`` is produced by fixed string templates over those integers only.
    """

    _require_tenant(session, tenant_id)
    day = briefing_date or (datetime.now(UTC) - timedelta(days=1)).date()
    start, end = _day_window(day)

    def count_day(model, column, *extra) -> int:
        stmt = select(func.count()).select_from(model).where(
            model.tenant_id == tenant_id, column >= start, column < end, *extra
        )
        return int(session.scalar(stmt) or 0)

    leads = count_day(Lead, Lead.created_at)
    visits_completed = int(
        session.scalar(
            select(func.count(Booking.id))
            .join(VisitSlot, Booking.slot_id == VisitSlot.id)
            .where(
                Booking.tenant_id == tenant_id,
                Booking.status == BookingStatus.COMPLETED.value,
                VisitSlot.start_time >= start,
                VisitSlot.start_time < end,
            )
        )
        or 0
    )
    bookings_created = count_day(Booking, Booking.created_at)
    bookings_cancelled = count_day(Booking, Booking.cancelled_at)
    sale_rows = session.execute(
        select(func.count(SaleBooking.id), func.coalesce(func.sum(SaleBooking.consideration_paise), 0))
        .where(
            SaleBooking.tenant_id == tenant_id,
            SaleBooking.booked_on == day,
            SaleBooking.status != SaleStatus.CANCELLED.value,
        )
    ).one()
    receipt_rows = session.execute(
        select(func.count(Receipt.id), func.coalesce(func.sum(Receipt.amount_paise), 0))
        .where(
            Receipt.tenant_id == tenant_id,
            *live_receipt_conditions(),
            Receipt.paid_at >= start,
            Receipt.paid_at < end,
        )
    ).one()
    tickets_created = count_day(Ticket, Ticket.created_at)
    tickets_resolved = count_day(Ticket, Ticket.resolved_at)
    approvals_decided = count_day(ApprovalRequest, ApprovalRequest.decided_at)

    active_lead_filter = (
        Lead.status.in_(ACTIVE_LEAD_STATUSES),
        Lead.opted_out.is_(False),
    )
    unassigned_active = int(
        session.scalar(
            select(func.count(Lead.id))
            .where(
                Lead.tenant_id == tenant_id,
                *active_lead_filter,
                ~exists(
                    select(LeadAssignment.id).where(
                        LeadAssignment.lead_id == Lead.id,
                        LeadAssignment.tenant_id == tenant_id,
                        LeadAssignment.unassigned_at.is_(None),
                    )
                ),
            )
        )
        or 0
    )
    active_bookings = int(
        session.scalar(
            select(func.count(SaleBooking.id)).where(
                SaleBooking.tenant_id == tenant_id,
                SaleBooking.status.notin_(NON_UNSOLD_SALE_STATUSES),
            )
        )
        or 0
    )
    approvals_pending = int(
        session.scalar(
            select(func.count(ApprovalRequest.id)).where(
                ApprovalRequest.tenant_id == tenant_id,
                ApprovalRequest.status == ApprovalStatus.PENDING.value,
            )
        )
        or 0
    )
    sla = ticket_sla_summary(session, tenant_id=tenant_id)
    overdue = overdue_installments(session, tenant_id=tenant_id, project_id=None, as_of=day + timedelta(days=1))

    counts = {
        "leads": leads,
        "visits_completed": visits_completed,
        "visit_bookings_created": bookings_created,
        "visit_bookings_cancelled": bookings_cancelled,
        "sale_bookings": int(sale_rows[0]),
        "sale_booking_value_paise": int(sale_rows[1]),
        "receipts": int(receipt_rows[0]),
        "receipts_paise": int(receipt_rows[1]),
        "tickets_created": tickets_created,
        "tickets_resolved": tickets_resolved,
        "approvals_decided": approvals_decided,
    }
    open_items = {
        "approvals_pending": approvals_pending,
        "tickets_breaching_sla": sla["breaching_count"],
        "overdue_installments": overdue["count"],
        "overdue_amount_paise": overdue["amount_paise"],
        "unassigned_active_leads": unassigned_active,
        "active_sale_bookings": active_bookings,
    }
    lines = _render_briefing_lines(day, counts, open_items)

    return {
        "briefing_date": day,
        "generated_at": datetime.now(UTC),
        "tenant_id": tenant_id,
        "counts": counts,
        "open_items": open_items,
        "lines": lines,
    }


def _render_briefing_lines(day: date, counts: dict, open_items: dict) -> list[str]:
    """Pure template rendering over the day's integers — deterministic by construction."""

    lines = [f"Morning briefing for {day.isoformat()} (UTC)."]
    lines.append(
        f"Yesterday: {counts['leads']} new enquiries, "
        f"{counts['visits_completed']} site visits completed, "
        f"{counts['sale_bookings']} sale bookings"
        + (
            f" worth {format_paise_indian(counts['sale_booking_value_paise'])}."
            if counts["sale_bookings"] > 0
            else "."
        )
    )
    if counts["receipts"] > 0:
        lines.append(
            f"Collections: {counts['receipts']} receipt(s) totalling "
            f"{format_paise_indian(counts['receipts_paise'])}."
        )
    else:
        lines.append("Collections: no payments received yesterday.")
    if counts["visit_bookings_created"] > 0 or counts["visit_bookings_cancelled"] > 0:
        lines.append(
            f"Visit schedule: {counts['visit_bookings_created']} booked, "
            f"{counts['visit_bookings_cancelled']} cancelled."
        )
    if counts["tickets_created"] > 0 or counts["tickets_resolved"] > 0:
        lines.append(
            f"Service desk: {counts['tickets_created']} new ticket(s), "
            f"{counts['tickets_resolved']} resolved."
        )
    if counts["approvals_decided"] > 0:
        lines.append(f"Approvals: {counts['approvals_decided']} decision(s) recorded.")
    if open_items["approvals_pending"] > 0:
        lines.append(f"Awaiting approval: {open_items['approvals_pending']} request(s).")
    if open_items["tickets_breaching_sla"] > 0:
        lines.append(
            f"SLA breach: {open_items['tickets_breaching_sla']} unresolved ticket(s) past due."
        )
    if open_items["overdue_installments"] > 0:
        lines.append(
            f"Overdue: {open_items['overdue_installments']} installment(s) outstanding "
            f"worth {format_paise_indian(open_items['overdue_amount_paise'])}."
        )
    if open_items["unassigned_active_leads"] > 0:
        lines.append(
            f"Coverage gap: {open_items['unassigned_active_leads']} active lead(s) "
            "without an assigned executive."
        )
    return lines
