"""Collections command centre service: calendar, promises, escalations, stats.

All money math reuses ``postsales.repository.live_receipt_conditions`` so
voided receipts never contribute to paid/outstanding/recovered totals.
Escalations are read-only: they compute a suggested action and record it in
the response only — no booking status, cancellation, or balance is ever
mutated here.
"""

from __future__ import annotations

import calendar as calendar_lib
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.collections.models import CollectionReminder, InstallmentPromise
from app.modules.collections.policy import resolve_policy
from app.modules.collections.reminders import last_reminder_map
from app.modules.documents.models import Document, DocumentStatus
from app.modules.leads.models import Lead
from app.modules.postsales import repository as postsales_repository
from app.modules.postsales.exceptions import InstallmentNotFoundError
from app.modules.postsales.models import (
    Installment,
    InstallmentStatus,
    PaymentPlan,
    Receipt,
    SaleBooking,
    SaleStatus,
)

# Statuses that still have collectible money. WAIVED/CANCELLED-like states
# are excluded from due/outstanding math.
OPEN_STATUSES = (
    InstallmentStatus.PENDING.value,
    InstallmentStatus.DUE.value,
    InstallmentStatus.PART_PAID.value,
    InstallmentStatus.OVERDUE.value,
)


def _installment_join_conditions(tenant_id: UUID):
    return (
        Installment.tenant_id == tenant_id,
        PaymentPlan.tenant_id == tenant_id,
        SaleBooking.tenant_id == tenant_id,
    )


def _base_rows(session: Session, *, tenant_id: UUID, project_id: UUID | None = None):
    """Joined installment/plan/booking rows, tenant-scoped throughout."""

    stmt = (
        select(Installment, PaymentPlan, SaleBooking)
        .join(PaymentPlan, PaymentPlan.id == Installment.plan_id)
        .join(SaleBooking, SaleBooking.id == PaymentPlan.sale_booking_id)
        .where(
            *_installment_join_conditions(tenant_id),
            PaymentPlan.is_active.is_(True),
            SaleBooking.status.not_in((SaleStatus.CANCELLED.value,)),
        )
    )
    if project_id is not None:
        stmt = stmt.where(SaleBooking.project_id == project_id)
    return list(session.execute(stmt).all())


def _paid_map(session: Session, *, tenant_id: UUID, installment_ids: list[UUID]) -> dict[UUID, int]:
    if not installment_ids:
        return {}
    rows = session.execute(
        select(Receipt.installment_id, func.coalesce(func.sum(Receipt.amount_paise), 0))
        .where(
            Receipt.tenant_id == tenant_id,
            Receipt.installment_id.in_(installment_ids),
            *postsales_repository.live_receipt_conditions(),
        )
        .group_by(Receipt.installment_id)
    ).all()
    return {row[0]: int(row[1] or 0) for row in rows}


def _paid_since_map(
    session: Session, *, tenant_id: UUID, promises: list[InstallmentPromise]
) -> dict[UUID, int]:
    """Live receipts paid after each promise was recorded, keyed by promise id.

    Used to decide whether a promise has been fulfilled: a promise is met once
    the buyer has paid the promised amount in the window after making it,
    regardless of how much was already paid on the installment beforehand.
    """

    installment_ids = list({p.installment_id for p in promises})
    if not installment_ids:
        return {}
    receipt_rows = session.scalars(
        select(Receipt).where(
            Receipt.tenant_id == tenant_id,
            Receipt.installment_id.in_(installment_ids),
            *postsales_repository.live_receipt_conditions(),
        )
    ).all()
    by_installment: dict[UUID, list[tuple[datetime, int]]] = {}
    for receipt in receipt_rows:
        paid_at = receipt.paid_at
        if paid_at.tzinfo is None:
            paid_at = paid_at.replace(tzinfo=UTC)
        by_installment.setdefault(receipt.installment_id, []).append(
            (paid_at, receipt.amount_paise)
        )
    result: dict[UUID, int] = {}
    for promise in promises:
        created = promise.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        total = sum(
            amount
            for paid_at, amount in by_installment.get(promise.installment_id, [])
            if paid_at >= created
        )
        result[promise.id] = total
    return result


def _lead_names(session: Session, *, tenant_id: UUID, lead_ids: list[UUID]) -> dict[UUID, str]:
    if not lead_ids:
        return {}
    rows = session.execute(
        select(Lead.id, Lead.full_name).where(
            Lead.tenant_id == tenant_id, Lead.id.in_(lead_ids),
        )
    ).all()
    return {row[0]: row[1] for row in rows}


def _demand_letter_status(
    session: Session, *, tenant_id: UUID, installment_ids: list[UUID]
) -> dict[UUID, str]:
    """Latest demand-letter document status per installment.

    Precedence when several documents exist: ISSUED > DRAFT > VOIDED, so a
    voided draft never hides the fact that a later letter was issued.
    """

    if not installment_ids:
        return {}
    rows = session.execute(
        select(Document.reference_id, Document.status, Document.created_at)
        .where(
            Document.tenant_id == tenant_id,
            Document.kind == "DEMAND_LETTER",
            Document.reference_type == "installment",
            Document.reference_id.in_(installment_ids),
        )
        .order_by(Document.created_at)
    ).all()
    precedence = {DocumentStatus.VOIDED.value: 0, DocumentStatus.DRAFT.value: 1, DocumentStatus.ISSUED.value: 2}
    result: dict[UUID, str] = {}
    rank: dict[UUID, int] = {}
    for reference_id, status, _created in rows:
        if rank.get(reference_id, -1) <= precedence.get(status, 0):
            result[reference_id] = status
            rank[reference_id] = precedence.get(status, 0)
    return result


def _aging_bucket(days_overdue: int) -> str:
    if days_overdue > 90:
        return "bucket_90_plus_paise"
    if days_overdue > 60:
        return "bucket_61_90_paise"
    if days_overdue > 30:
        return "bucket_31_60_paise"
    return "bucket_1_30_paise"


def _empty_aging() -> dict[str, int]:
    return {
        "bucket_1_30_paise": 0,
        "bucket_31_60_paise": 0,
        "bucket_61_90_paise": 0,
        "bucket_90_plus_paise": 0,
    }


def calendar(
    session: Session,
    *,
    tenant_id: UUID,
    month: str,
    project_id: UUID | None = None,
    today: date | None = None,
) -> dict:
    """Dynamic payment calendar: installments due in ``month`` grouped by day.

    Overdue aging is computed against ALL outstanding installments of the
    tenant (optionally project-filtered), not only those in the requested
    month, so the 30/60/90+ buckets stay meaningful when viewing any month.
    """

    try:
        year, mon = int(month[:4]), int(month[5:7])
        if not 1 <= mon <= 12 or len(month) != 7 or month[4] != "-":
            raise ValueError
    except ValueError:
        raise ValueError("month must be formatted YYYY-MM") from None
    day = today or date.today()
    last_day = calendar_lib.monthrange(year, mon)[1]
    month_start, month_end = date(year, mon, 1), date(year, mon, last_day)

    rows = _base_rows(session, tenant_id=tenant_id, project_id=project_id)
    installment_ids = [inst.id for inst, _plan, _booking in rows]
    paid = _paid_map(session, tenant_id=tenant_id, installment_ids=installment_ids)
    names = _lead_names(
        session, tenant_id=tenant_id, lead_ids=[b.lead_id for _i, _p, b in rows],
    )
    last_reminders = last_reminder_map(session, tenant_id=tenant_id, installment_ids=installment_ids)
    demand_status = _demand_letter_status(session, tenant_id=tenant_id, installment_ids=installment_ids)
    # Overdue promises: promised_on has passed and the promise is still
    # unfulfilled. A promise is a commitment to pay ``amount_paise``; it is
    # fulfilled once live receipts paid SINCE the promise was recorded reach
    # that amount. Comparing against the installment's lifetime total would
    # wrongly keep a remaining-balance promise overdue on a part-paid
    # installment even after the buyer pays the promised remainder.
    overdue_promises: set[UUID] = set()
    if installment_ids:
        promise_rows = session.scalars(
            select(InstallmentPromise).where(
                InstallmentPromise.tenant_id == tenant_id,
                InstallmentPromise.installment_id.in_(installment_ids),
                InstallmentPromise.promised_on < day,
            )
        ).all()
        if promise_rows:
            paid_since = _paid_since_map(
                session,
                tenant_id=tenant_id,
                promises=promise_rows,
            )
            for promise in promise_rows:
                if paid_since.get(promise.id, 0) < promise.amount_paise:
                    overdue_promises.add(promise.installment_id)

    days_map: dict[date, dict] = {}
    aging = _empty_aging()
    due_this_month = 0
    for installment, plan, booking in rows:
        live_paid = paid.get(installment.id, 0)
        outstanding = max(0, installment.amount_paise - live_paid)
        days_overdue = max(0, (day - installment.due_on).days)
        is_open = (
            installment.status in OPEN_STATUSES
            and live_paid < installment.amount_paise
        )
        if is_open and days_overdue > 0:
            aging[_aging_bucket(days_overdue)] += outstanding

        if not (month_start <= installment.due_on <= month_end):
            continue
        due_this_month += outstanding if is_open else 0
        entry = days_map.setdefault(installment.due_on, {"rows": [], "due_paise": 0})
        if is_open:
            entry["due_paise"] += outstanding
        entry["rows"].append({
            "installment_id": installment.id,
            "booking_id": booking.id,
            "plan_id": plan.id,
            "project_id": booking.project_id,
            "customer_name": names.get(booking.lead_id),
            "unit_number": booking.unit_number,
            "milestone": installment.milestone,
            "due_on": installment.due_on,
            "amount_paise": installment.amount_paise,
            "paid_paise": live_paid,
            "outstanding_paise": outstanding,
            "status": installment.status,
            "days_overdue": days_overdue if is_open else 0,
            "demand_letter_status": demand_status.get(installment.id, "NOT_SENT"),
            "demand_letter_sent_at": installment.demand_letter_sent_at,
            "last_reminder_at": last_reminders.get(installment.id),
            "has_overdue_promise": installment.id in overdue_promises,
        })

    days = [
        {"date": due_on, "due_paise": data["due_paise"], "rows": data["rows"]}
        for due_on, data in sorted(days_map.items())
    ]
    return {
        "month": month,
        "project_id": project_id,
        "days": days,
        "overdue_aging": aging,
        "due_this_month_paise": due_this_month,
    }


# ---------------------------------------------------------------------------
# Promises
# ---------------------------------------------------------------------------

def create_promise(
    session: Session,
    *,
    actor,
    installment_id: UUID,
    amount_paise: int,
    promised_on: date,
    note: str | None,
) -> InstallmentPromise:
    """Record a payment promise. NEVER touches installment/receipt balances."""

    installment = postsales_repository.get_installment(
        session, installment_id, tenant_id=actor.tenant_id,
    )
    if installment is None:
        raise InstallmentNotFoundError()
    row = InstallmentPromise(
        tenant_id=actor.tenant_id,
        installment_id=installment.id,
        amount_paise=amount_paise,
        promised_on=promised_on,
        note=note,
        created_by_id=actor.id,
    )
    session.add(row)
    session.flush()
    return row


def list_promises(
    session: Session, *, tenant_id: UUID, installment_id: UUID
) -> list[InstallmentPromise]:
    installment = postsales_repository.get_installment(
        session, installment_id, tenant_id=tenant_id,
    )
    if installment is None:
        raise InstallmentNotFoundError()
    return list(
        session.scalars(
            select(InstallmentPromise)
            .where(
                InstallmentPromise.tenant_id == tenant_id,
                InstallmentPromise.installment_id == installment_id,
            )
            .order_by(InstallmentPromise.created_at.desc())
        ).all()
    )


# ---------------------------------------------------------------------------
# Escalations
# ---------------------------------------------------------------------------

def _severity_for(days_overdue: int, thresholds: dict[str, int]) -> str | None:
    if days_overdue >= thresholds["severe"]:
        return "severe"
    if days_overdue >= thresholds["critical"]:
        return "critical"
    if days_overdue >= thresholds["warning"]:
        return "warning"
    return None


_SUGGESTED_ACTIONS = {
    "warning": "Send a reminder and call the customer to confirm a payment date.",
    "critical": "Issue a demand letter and schedule a senior collections follow-up.",
    "severe": "Escalate to management; review the account under the existing cancellation engine.",
}


def escalations(
    session: Session,
    *,
    tenant_id: UUID,
    project_id: UUID | None = None,
    today: date | None = None,
) -> dict:
    """Group accounts crossing age thresholds by severity. Read-only."""

    day = today or date.today()
    policy = resolve_policy(session, tenant_id=tenant_id)
    thresholds = policy["escalation_thresholds"]
    rows = _base_rows(session, tenant_id=tenant_id, project_id=project_id)
    installment_ids = [inst.id for inst, _p, _b in rows]
    paid = _paid_map(session, tenant_id=tenant_id, installment_ids=installment_ids)
    names = _lead_names(session, tenant_id=tenant_id, lead_ids=[b.lead_id for _i, _p, b in rows])
    last_reminders = last_reminder_map(session, tenant_id=tenant_id, installment_ids=installment_ids)
    demand_status = _demand_letter_status(session, tenant_id=tenant_id, installment_ids=installment_ids)

    accounts: dict[UUID, dict] = {}
    severity_rank = {"warning": 1, "critical": 2, "severe": 3}
    for installment, plan, booking in rows:
        live_paid = paid.get(installment.id, 0)
        if live_paid >= installment.amount_paise:
            continue
        if installment.status not in OPEN_STATUSES:
            continue
        days_overdue = (day - installment.due_on).days
        if days_overdue <= 0:
            # Not yet overdue: contributes nothing to a collections account.
            continue
        # Aggregate ALL open overdue installments so an account's
        # outstanding_paise / overdue_installments reflect the whole arrears,
        # including recent rows below the warning band. Severity is assigned
        # afterwards from the worst (oldest) overdue age.
        severity = _severity_for(days_overdue, thresholds) or "warning"
        outstanding = max(0, installment.amount_paise - live_paid)
        account = accounts.setdefault(booking.id, {
            "booking": booking,
            "oldest_due_on": installment.due_on,
            "days_overdue": 0,
            "outstanding_paise": 0,
            "overdue_installments": 0,
            "severity_rank": 0,
            "installment_ids": [],
        })
        account["outstanding_paise"] += outstanding
        account["overdue_installments"] += 1
        account["installment_ids"].append(installment.id)
        if days_overdue > account["days_overdue"]:
            account["days_overdue"] = days_overdue
            account["oldest_due_on"] = installment.due_on
        # Track the worst severity across the booking's installments.
        rank = severity_rank[severity]
        if rank > account["severity_rank"]:
            account["severity_rank"] = rank
            account["severity"] = severity

    groups: dict[str, list[dict]] = {"warning": [], "critical": [], "severe": []}
    # Drop accounts that never actually crossed the warning threshold (all
    # their overdue rows are younger than the warning band).
    accounts = {
        booking_id: account
        for booking_id, account in accounts.items()
        if _severity_for(account["days_overdue"], thresholds) is not None
    }
    for account in accounts.values():
        booking = account["booking"]
        severity = account["severity"]
        last_actions = {
            "last_reminder_at": max(
                (last_reminders[iid] for iid in account["installment_ids"] if iid in last_reminders),
                default=None,
            ),
            "demand_letter_status": "NOT_SENT",
        }
        statuses = {
            demand_status[iid] for iid in account["installment_ids"] if iid in demand_status
        }
        if DocumentStatus.ISSUED.value in statuses:
            last_actions["demand_letter_status"] = DocumentStatus.ISSUED.value
        elif DocumentStatus.DRAFT.value in statuses:
            last_actions["demand_letter_status"] = DocumentStatus.DRAFT.value
        elif DocumentStatus.VOIDED.value in statuses:
            last_actions["demand_letter_status"] = DocumentStatus.VOIDED.value
        groups[severity].append({
            "booking_id": booking.id,
            "project_id": booking.project_id,
            "customer_name": names.get(booking.lead_id),
            "unit_number": booking.unit_number,
            "severity": severity,
            "oldest_due_on": account["oldest_due_on"],
            "days_overdue": account["days_overdue"],
            "outstanding_paise": account["outstanding_paise"],
            "overdue_installments": account["overdue_installments"],
            "last_actions": last_actions,
            "suggested_action": _SUGGESTED_ACTIONS[severity],
        })
    for bucket in groups.values():
        bucket.sort(key=lambda row: row["days_overdue"], reverse=True)
    return {"groups": groups, "thresholds": thresholds}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def stats(
    session: Session,
    *,
    tenant_id: UUID,
    project_id: UUID | None = None,
    now: datetime | None = None,
) -> dict:
    """Collections analytics: recovered windows, aging, reminder/payment counts.

    ``reminder_payment_counts`` reports measurable counts only: how many
    reminders were queued and how many live receipts landed within 30 days
    after a reminder on the same installment. It is NOT a causal conversion
    rate — no attribution claim is made.
    """

    timestamp = now or datetime.now(UTC)
    day = timestamp.date()
    rows = _base_rows(session, tenant_id=tenant_id, project_id=project_id)
    installment_ids = [inst.id for inst, _p, _b in rows]
    paid = _paid_map(session, tenant_id=tenant_id, installment_ids=installment_ids)

    recovered_30 = recovered_90 = 0
    if installment_ids:
        receipt_rows = session.scalars(
            select(Receipt).where(
                Receipt.tenant_id == tenant_id,
                Receipt.installment_id.in_(installment_ids),
                *postsales_repository.live_receipt_conditions(),
            )
        ).all()
        for receipt in receipt_rows:
            paid_at = receipt.paid_at
            if paid_at.tzinfo is None:
                paid_at = paid_at.replace(tzinfo=UTC)
            age = (timestamp - paid_at).days
            if 0 <= age <= 30:
                recovered_30 += receipt.amount_paise
            if 0 <= age <= 90:
                recovered_90 += receipt.amount_paise
    else:
        receipt_rows = []

    aging = _empty_aging()
    outstanding_total = 0
    for installment, _plan, _booking in rows:
        live_paid = paid.get(installment.id, 0)
        if installment.status not in OPEN_STATUSES or live_paid >= installment.amount_paise:
            continue
        outstanding = max(0, installment.amount_paise - live_paid)
        days_overdue = (day - installment.due_on).days
        if days_overdue > 0:
            aging[_aging_bucket(days_overdue)] += outstanding
        outstanding_total += outstanding

    reminders = (
        list(session.scalars(
            select(CollectionReminder).where(
                CollectionReminder.tenant_id == tenant_id,
                CollectionReminder.installment_id.in_(installment_ids),
            )
        ).all())
        if installment_ids
        else []
    )
    payments_after = 0
    if reminders and receipt_rows:
        receipts_by_installment: dict[UUID, list[Receipt]] = {}
        for receipt in receipt_rows:
            receipts_by_installment.setdefault(receipt.installment_id, []).append(receipt)
        matched_receipts: set[UUID] = set()
        for reminder in reminders:
            queued = reminder.queued_at
            if queued.tzinfo is None:
                queued = queued.replace(tzinfo=UTC)
            for receipt in receipts_by_installment.get(reminder.installment_id, []):
                if receipt.id in matched_receipts:
                    continue
                paid_at = receipt.paid_at
                if paid_at.tzinfo is None:
                    paid_at = paid_at.replace(tzinfo=UTC)
                if queued <= paid_at <= queued + timedelta(days=30):
                    payments_after += 1
                    matched_receipts.add(receipt.id)

    return {
        "project_id": project_id,
        "recovered_30d_paise": recovered_30,
        "recovered_90d_paise": recovered_90,
        "outstanding_paise": outstanding_total,
        "aging_buckets_paise": aging,
        "reminder_payment_counts": {
            "reminders_queued": len(reminders),
            "payments_after_reminder": payments_after,
        },
    }


def get_policy(session: Session, *, tenant_id: UUID) -> dict:
    return resolve_policy(session, tenant_id=tenant_id)


def upsert_policy(session: Session, *, actor, value: dict) -> dict:
    """Validate and persist the tenant policy (admin writes)."""

    from app.modules.collections.policy import validate_policy
    from app.modules.settings.repository import upsert_setting

    cleaned = validate_policy(value)
    upsert_setting(
        session,
        tenant_id=actor.tenant_id,
        key="collections_reminder_policy",
        category="REMINDERS",
        value=cleaned,
        description="Collections reminder sequence and escalation thresholds.",
        updated_by_id=actor.id,
    )
    session.flush()
    return resolve_policy(session, tenant_id=actor.tenant_id)
