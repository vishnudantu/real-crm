"""Operator-side revenue aggregation.

Read-only over existing billing tables; nothing here writes data or changes a
subscription. Each function documents its source queries.

Dialect note: date bucketing mirrors ``dashboard.repository`` (SQLite uses
``strftime``; PostgreSQL uses ``date_trunc``), normalized to ``date`` in Python.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.billing.models import (
    BillingWebhookEvent,
    Invoice,
    Subscription,
    SubscriptionStatus,
)
from app.modules.billing.service import (
    _count_active_users,
    _count_period_leads,
    _count_period_whatsapp_sent,
    _current_usage_window,
    current_plan,
)
from app.modules.plans.models import Plan
from app.modules.tenancy.models import Tenant

#: A usage meter at or above this share of its plan limit is an expansion signal.
EXPANSION_USAGE_RATIO = 0.8

REVENUE_MONTHS_DEFAULT = 6
REVENUE_MONTHS_MAX = 24
RENEWAL_WINDOW_DAYS = 30
EVENT_PROVIDER = "razorpay"

_CRORE_PAISE = 1_00_00_00_00  # ₹1,00,00,000 expressed in paise
_LAKH_PAISE = 1_00_00_00      # ₹1,00,000 expressed in paise


def _month_bucket(session: Session, column):
    """SQL expression that buckets a timestamp column to its month start."""

    dialect = session.get_bind().dialect.name
    if dialect == "sqlite":
        return func.date(column, "start of month")
    # PostgreSQL: TIMESTAMPTZ + date_trunc yields timestamptz; cast to date.
    return func.cast(func.date_trunc("month", column), date)


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


# ---------------------------------------------------------------------------
# Recurring revenue (MRR / ARR)
# ---------------------------------------------------------------------------


def recurring_revenue(session: Session) -> dict:
    """MRR/ARR from the latest ACTIVE subscription per tenant.

    Source query: the tenant's most recent row in ``subscriptions`` ordered by
    ``created_at`` DESC (the same "latest subscription" rule as
    ``billing.service``), joined to its ``plan.price_paise``. Only tenants whose
    latest subscription is ACTIVE count toward MRR; PAST_DUE and HALTED are
    reported separately so the operator sees at-risk revenue, not silent churn.
    The plan price is the monthly amount (Plan is defined in monthly paise).
    """

    latest = (
        select(
            Subscription.tenant_id,
            func.row_number()
            .over(
                partition_by=Subscription.tenant_id,
                order_by=(Subscription.created_at.desc(), Subscription.id.desc()),
            )
            .label("rn"),
        )
        .subquery()
    )
    rows = session.execute(
        select(
            Subscription.status,
            func.count(Subscription.id),
            func.coalesce(func.sum(Plan.price_paise), 0),
        )
        .select_from(Subscription)
        .join(latest, latest.c.tenant_id == Subscription.tenant_id)
        .join(Plan, Subscription.plan_id == Plan.id)
        .where(latest.c.rn == 1)
        .group_by(Subscription.status)
    ).all()

    by_status = {row[0]: (int(row[1]), int(row[2])) for row in rows}
    active_count, active_paise = by_status.get(SubscriptionStatus.ACTIVE.value, (0, 0))
    past_due_count, past_due_paise = by_status.get(SubscriptionStatus.PAST_DUE.value, (0, 0))
    halted_count, halted_paise = by_status.get(SubscriptionStatus.HALTED.value, (0, 0))

    return {
        "mrr_paise": active_paise,
        "arr_paise": active_paise * 12,
        "active_subscriptions": active_count,
        "at_risk": {
            "past_due_count": past_due_count,
            "past_due_mrr_paise": past_due_paise,
            "halted_count": halted_count,
            "halted_mrr_paise": halted_paise,
        },
    }


# ---------------------------------------------------------------------------
# Invoiced revenue trend + payment failures
# ---------------------------------------------------------------------------


def invoiced_by_month(
    session: Session, *, months: int = REVENUE_MONTHS_DEFAULT
) -> list[dict]:
    """Paid invoice totals per calendar month.

    Source query: SUM/COUNT over ``invoices`` (``status = 'paid'``) grouped by
    month of ``invoices.paid_at`` — the money actually captured, distinct from
    the MRR plan-price snapshot above.
    """

    today = datetime.now(UTC).date()
    window_start = _month_grid(months, today)[0]
    bucket = _month_bucket(session, Invoice.paid_at)

    rows = session.execute(
        select(
            bucket.label("m"),
            func.coalesce(func.sum(Invoice.amount_paise), 0),
            func.count(Invoice.id),
        )
        .where(Invoice.status == "paid", Invoice.paid_at >= window_start)
        .group_by(bucket)
    ).all()

    totals = {_as_date(r[0]): (int(r[1]), int(r[2])) for r in rows}
    return [
        {
            "month": month,
            "invoiced_paise": totals.get(month, (0, 0))[0],
            "invoice_count": totals.get(month, (0, 0))[1],
        }
        for month in _month_grid(months, today)
    ]


def payment_failures(session: Session, *, since: datetime) -> dict:
    """Failed payment events in the provider ledger since a timestamp.

    Source query: COUNT over ``billing_webhook_events`` where
    ``event_type = 'payment.failed'`` and ``processed_at >= since``. The ledger
    is provider-deduplicated by ``event_id``, so retries never double-count.
    """

    count = int(
        session.scalar(
            select(func.count(BillingWebhookEvent.id)).where(
                BillingWebhookEvent.provider == EVENT_PROVIDER,
                BillingWebhookEvent.event_type == "payment.failed",
                BillingWebhookEvent.processed_at >= since,
            )
        )
        or 0
    )
    affected = int(
        session.scalar(
            select(func.count(func.distinct(Subscription.tenant_id)))
            .where(Subscription.status == SubscriptionStatus.HALTED.value)
        )
        or 0
    )
    return {"count_last_30_days": count, "halted_tenants": affected}


# ---------------------------------------------------------------------------
# Expansion signals (usage meters near plan limits)
# ---------------------------------------------------------------------------


def expansion_signals(session: Session, *, limit: int = 20) -> list[dict]:
    """Tenants at ≥ 80% of a monthly plan limit — the upsell list.

    Reuses the billing usage-meter primitives (``billing.service`` counters and
    ``_current_usage_window``) per tenant with a live plan:

      * leads — COUNT(leads.created_at) inside the tenant's usage window vs
        ``plan.leads_per_month``.
      * whatsapp_sent — SENT WhatsApp MessageDelivery rows in the window vs
        ``plan.whatsapp_msgs_per_month``.
      * users — active-user count vs ``plan.max_users`` (seat meter).

    A signal is emitted per (tenant, meter) where used/limit ≥ 0.8. Tenants are
    sorted by the highest ratio first.
    """

    tenants = session.scalars(select(Tenant).order_by(Tenant.name)).all()
    signals: list[dict] = []

    for tenant in tenants:
        plan = current_plan(session, tenant_id=tenant.id)
        if plan is None:
            continue
        start, end, source = _current_usage_window(session, tenant_id=tenant.id)
        meters = {
            "leads": (
                _count_period_leads(session, tenant_id=tenant.id, start=start, end=end),
                plan.leads_per_month,
            ),
            "whatsapp_sent": (
                _count_period_whatsapp_sent(session, tenant_id=tenant.id, start=start, end=end),
                plan.whatsapp_msgs_per_month,
            ),
            "users": (_count_active_users(session, tenant_id=tenant.id), plan.max_users),
        }
        for meter, (used, cap) in meters.items():
            if cap <= 0:
                continue
            ratio = used / cap
            if ratio < EXPANSION_USAGE_RATIO:
                continue
            signals.append(
                {
                    "tenant_id": tenant.id,
                    "tenant_slug": tenant.slug,
                    "tenant_name": tenant.name,
                    "meter": meter,
                    "used": used,
                    "limit": cap,
                    "ratio": round(min(ratio, 1.0), 4),
                    "period_source": source,
                }
            )

    signals.sort(key=lambda s: (-s["ratio"], s["tenant_name"], s["meter"]))
    return signals[:limit]


# ---------------------------------------------------------------------------
# Renewals
# ---------------------------------------------------------------------------


def renewals_due(
    session: Session, *, within_days: int = RENEWAL_WINDOW_DAYS
) -> dict:
    """Subscriptions whose current period ends within the next window.

    Source query: ``subscriptions`` with ``status = 'active'`` and
    ``current_period_end`` in ``[now, now + within_days]`` (inclusive), joined
    to plan price for the renewal MRR at stake.
    """

    now = datetime.now(UTC)
    horizon = now + timedelta(days=within_days)
    rows = session.execute(
        select(Subscription, Tenant.slug, Tenant.name, Plan.name, Plan.price_paise)
        .join(Tenant, Subscription.tenant_id == Tenant.id)
        .join(Plan, Subscription.plan_id == Plan.id)
        .where(
            Subscription.status == SubscriptionStatus.ACTIVE.value,
            Subscription.current_period_end.is_not(None),
            Subscription.current_period_end >= now,
            Subscription.current_period_end <= horizon,
        )
        .order_by(Subscription.current_period_end.asc())
    ).all()

    upcoming = [
        {
            "tenant_id": sub.tenant_id,
            "tenant_slug": slug,
            "tenant_name": name,
            "plan_name": plan_name,
            "period_end": _as_date(sub.current_period_end),
            "days_until": max((_as_date(sub.current_period_end) - now.date()).days, 0),
            "price_paise": int(price),
        }
        for sub, slug, name, plan_name, price in rows
    ]
    return {
        "window_days": within_days,
        "count": len(upcoming),
        "mrr_at_stake_paise": sum(row["price_paise"] for row in upcoming),
        "subscriptions": upcoming,
    }


# ---------------------------------------------------------------------------
# Summary assembly
# ---------------------------------------------------------------------------


def revenue_summary(session: Session, *, months: int = REVENUE_MONTHS_DEFAULT) -> dict:
    """Assemble the operator Revenue Command Centre payload (read-only).

    Combines :func:`recurring_revenue`, :func:`invoiced_by_month`,
    :func:`payment_failures`, :func:`expansion_signals`, and
    :func:`renewals_due`; each section's docstring names its source tables and
    filters. ``months`` is clamped to 1..24.
    """

    months = min(max(months, 1), REVENUE_MONTHS_MAX)
    since = datetime.now(UTC) - timedelta(days=30)
    return {
        "generated_at": datetime.now(UTC),
        "window_months": months,
        **recurring_revenue(session),
        "invoiced": invoiced_by_month(session, months=months),
        "failures": payment_failures(session, since=since),
        "expansion_signals": expansion_signals(session),
        "renewals": renewals_due(session),
    }
