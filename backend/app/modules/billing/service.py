"""Razorpay signature verification, subscription lifecycle, and usage enforcement."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.billing.models import (
    BillingWebhookEvent,
    Invoice,
    Subscription,
    SubscriptionStatus,
)
from app.modules.leads.models import Lead
from app.modules.messaging.models import MessageDelivery
from app.modules.plans.models import Plan
from app.modules.tenancy.models import Tenant, TenantStatus
from app.modules.users.models import User


class PlanLimitExceededError(HTTPException):
    """Return HTTP 402 Payment Required for an exhausted plan limit.

    For monthly meters the detail carries the period window (UTC ISO-8601) plus
    used/limit so the UI can render "3 of 1,000 leads this month". INR/IST
    display conversion is a UI concern; the API always reports UTC.
    """

    def __init__(
        self,
        resource: str,
        limit: int,
        *,
        used: int | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        period_source: str | None = None,
    ) -> None:
        detail: dict = {
            "code": "PLAN_LIMIT_EXCEEDED",
            "message": f"Your plan's {resource} limit ({limit}) has been reached. Upgrade to continue.",
        }
        if used is not None:
            detail["used"] = used
            detail["limit"] = limit
        if used is not None and period_start is not None and period_end is not None:
            detail["period_start"] = period_start.isoformat()
            detail["period_end"] = period_end.isoformat()
            detail["period_source"] = period_source
            detail["message"] = (
                f"Your plan's {resource} limit has been reached: "
                f"{used} of {limit} in the current period "
                f"({period_start.date().isoformat()} to {period_end.date().isoformat()}). "
                "Upgrade to continue."
            )
        super().__init__(status.HTTP_402_PAYMENT_REQUIRED, detail)


def verify_razorpay_signature(raw_body: bytes, signature: str, settings: Settings) -> bool:
    """Verify X-Razorpay-Signature against the configured webhook secret."""

    secret = settings.razorpay_webhook_secret
    if secret is None or not signature:
        return False
    expected = hmac.new(
        secret.get_secret_value().encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def create_subscription(
    session: Session,
    *,
    tenant_id: UUID,
    plan_id: UUID,
    settings: Settings,
) -> Subscription:
    """Create a subscription in CREATED state; provider linkage follows at checkout."""

    plan = session.get(Plan, plan_id)
    if plan is None or not plan.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "An active plan is required.")
    now = datetime.now(UTC)
    row = Subscription(
        tenant_id=tenant_id,
        plan_id=plan_id,
        status=SubscriptionStatus.CREATED.value,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _record_event(session: Session, *, event_id: str, event_type: str, payload: dict) -> bool:
    """Record a provider event once; duplicate event IDs are a no-op."""

    event = BillingWebhookEvent(
        provider="razorpay", event_id=event_id, event_type=event_type, payload=payload
    )
    session.add(event)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        return False
    return True


def _apply_lifecycle(
    session: Session,
    *,
    subscription: Subscription,
    event_type: str,
    settings: Settings,
) -> None:
    now = datetime.now(UTC)
    if event_type in ("subscription.activated", "subscription.charged", "payment.captured"):
        subscription.status = SubscriptionStatus.ACTIVE.value
        subscription.current_period_start = now
        subscription.current_period_end = now + timedelta(days=30)
        tenant = session.get(Tenant, subscription.tenant_id)
        if tenant is not None and tenant.status != TenantStatus.ACTIVE.value:
            tenant.status = TenantStatus.ACTIVE.value
            session.add(tenant)
    elif event_type in ("subscription.halted", "subscription.paused", "payment.failed"):
        subscription.status = SubscriptionStatus.HALTED.value
        subscription.grace_period_end = now + timedelta(days=settings.plan_grace_days)
        tenant = session.get(Tenant, subscription.tenant_id)
        if tenant is not None:
            tenant.status = TenantStatus.SUSPENDED.value if settings.plan_grace_days == 0 else tenant.status
    elif event_type == "subscription.cancelled":
        subscription.status = SubscriptionStatus.CANCELLED.value
        tenant = session.get(Tenant, subscription.tenant_id)
        if tenant is not None:
            tenant.status = TenantStatus.SUSPENDED.value
    subscription.updated_at = now
    session.add(subscription)


def process_webhook(
    session: Session,
    *,
    raw_body: bytes,
    signature: str,
    settings: Settings,
) -> dict:
    """Verify, record once, and apply a Razorpay event's tenant lifecycle."""

    if not verify_razorpay_signature(raw_body, signature, settings):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid Razorpay signature.")
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid JSON payload.") from None

    event_type = payload.get("event", "")
    subscription_entity = (
        payload.get("payload", {}).get("subscription", {}).get("entity", {})
    )
    provider_id = subscription_entity.get("id") or payload.get("account_id", "")
    event_id = f"razorpay:{provider_id}:{event_type}:{payload.get('created_at', '')}"
    if not _record_event(session, event_id=event_id, event_type=event_type, payload=payload):
        return {"status": "duplicate"}

    subscription = session.scalar(
        select(Subscription).where(Subscription.razorpay_subscription_id == provider_id)
    )
    if subscription is None:
        return {"status": "unmapped"}
    _apply_lifecycle(session, subscription=subscription, event_type=event_type, settings=settings)

    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    if payment_entity.get("id") and payment_entity.get("status") == "captured":
        invoice = Invoice(
            tenant_id=subscription.tenant_id,
            subscription_id=subscription.id,
            razorpay_invoice_id=str(payment_entity["id"]),
            amount_paise=int(payment_entity.get("amount", 0)),
            currency=payment_entity.get("currency", "INR"),
            status="paid",
            paid_at=datetime.now(UTC),
        )
        session.add(invoice)
    session.commit()
    return {"status": "processed", "subscription_status": subscription.status}


def current_plan(session: Session, *, tenant_id: UUID) -> Plan | None:
    subscription = session.scalar(
        select(Subscription)
        .where(Subscription.tenant_id == tenant_id)
        .order_by(Subscription.created_at.desc())
    )
    if subscription is not None:
        plan = session.get(Plan, subscription.plan_id)
        if plan is not None:
            return plan
    tenant = session.get(Tenant, tenant_id)
    if tenant is not None and tenant.plan_id is not None:
        return session.get(Plan, tenant.plan_id)
    return None


def _latest_subscription(session: Session, *, tenant_id: UUID) -> Subscription | None:
    return session.scalar(
        select(Subscription)
        .where(Subscription.tenant_id == tenant_id)
        .order_by(Subscription.created_at.desc())
    )


def _as_utc(value: datetime) -> datetime:
    """Normalize a stored period timestamp to timezone-aware UTC.

    Postgres returns aware datetimes for TIMESTAMPTZ; SQLite (tests) returns
    naive values that were written as UTC. Naive input is interpreted as UTC.
    """

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _current_usage_window(
    session: Session, *, tenant_id: UUID
) -> tuple[datetime, datetime, str]:
    """Resolve the metering window for monthly plan limits.

    Returns (start_utc, end_utc, label). All datetimes are timezone-aware UTC;
    INR/IST presentation is a UI concern only.

    - SUBSCRIPTION: the latest subscription with both period bounds set uses
      its current_period_start (inclusive) .. current_period_end (inclusive).
    - ROLLING_30D: when there is no subscription, or it has no period bounds
      (grace/trial/dev tenant with an attached plan), use a rolling 30-day
      window ending now: [now - 30 days, now].
    """

    now = datetime.now(UTC)
    subscription = _latest_subscription(session, tenant_id=tenant_id)
    if (
        subscription is not None
        and subscription.current_period_start is not None
        and subscription.current_period_end is not None
    ):
        return (
            _as_utc(subscription.current_period_start),
            _as_utc(subscription.current_period_end),
            "SUBSCRIPTION",
        )
    return now - timedelta(days=30), now, "ROLLING_30D"


def _count_period_leads(
    session: Session, *, tenant_id: UUID, start: datetime, end: datetime
) -> int:
    """Count leads created inside the period window (start inclusive, end inclusive)."""

    return (
        session.scalar(
            select(func.count(Lead.id)).where(
                Lead.tenant_id == tenant_id,
                Lead.created_at >= start,
                Lead.created_at <= end,
            )
        )
        or 0
    )


def _count_period_whatsapp_sent(
    session: Session, *, tenant_id: UUID, start: datetime, end: datetime
) -> int:
    """Count SENT WhatsApp deliveries inside the period window.

    The dispatcher stamps sent_at at send time, so sent_at is authoritative.
    For legacy SENT rows where sent_at is NULL, fall back to created_at for the
    window check (COALESCE(sent_at, created_at)).
    """

    occurred_at = func.coalesce(MessageDelivery.sent_at, MessageDelivery.created_at)
    return (
        session.scalar(
            select(func.count(MessageDelivery.id)).where(
                MessageDelivery.tenant_id == tenant_id,
                MessageDelivery.channel == "WHATSAPP",
                MessageDelivery.status == "SENT",
                occurred_at >= start,
                occurred_at <= end,
            )
        )
        or 0
    )


def _count_active_users(session: Session, *, tenant_id: UUID) -> int:
    """Count active users for the seat limit; inactive accounts do not hold seats."""

    return (
        session.scalar(
            select(func.count(User.id)).where(
                User.tenant_id == tenant_id,
                User.is_active.is_(True),
            )
        )
        or 0
    )


def _usage_snapshot(
    session: Session, *, tenant_id: UUID
) -> tuple[dict, tuple[datetime, datetime, str]]:
    """Compute period usage for all meters plus the window used."""

    start, end, label = _current_usage_window(session, tenant_id=tenant_id)
    usage = {
        "users": _count_active_users(session, tenant_id=tenant_id),
        "leads": _count_period_leads(session, tenant_id=tenant_id, start=start, end=end),
        "whatsapp_sent": _count_period_whatsapp_sent(
            session, tenant_id=tenant_id, start=start, end=end
        ),
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "period_source": label,
    }
    return usage, (start, end, label)


def summary(session: Session, *, tenant_id: UUID) -> dict:
    """Return plan, subscription, period usage, and recent invoices for the tenant.

    Monthly meters (leads, whatsapp_sent) reflect the current usage window, not
    lifetime totals; users is an active-seat count. The usage payload includes
    the period window (UTC ISO-8601) and its source for UI display.
    """

    plan = current_plan(session, tenant_id=tenant_id)
    subscription = _latest_subscription(session, tenant_id=tenant_id)
    usage, _window = _usage_snapshot(session, tenant_id=tenant_id)
    invoices = list(
        session.scalars(
            select(Invoice)
            .where(Invoice.tenant_id == tenant_id)
            .order_by(Invoice.created_at.desc())
            .limit(25)
        ).all()
    )
    return {"plan": plan, "subscription": subscription, "usage": usage, "invoices": invoices}


def ensure_within_plan_limits(session: Session, *, tenant_id: UUID, kind: str) -> None:
    """Reject user/lead/WhatsApp creation when the tenant's plan limit is reached.

    users is a seat limit counted over active users. leads and whatsapp are
    monthly meters counted inside the current usage window (subscription period
    when available, else a rolling 30-day window).
    """

    plan = current_plan(session, tenant_id=tenant_id)
    if plan is None:
        return  # No plan = ungated development tenant.

    window: tuple[datetime, datetime, str] | None = None
    if kind == "users":
        used = _count_active_users(session, tenant_id=tenant_id)
        limit = plan.max_users
    elif kind == "leads":
        start, end, label = _current_usage_window(session, tenant_id=tenant_id)
        window = (start, end, label)
        used = _count_period_leads(session, tenant_id=tenant_id, start=start, end=end)
        limit = plan.leads_per_month
    elif kind == "whatsapp":
        start, end, label = _current_usage_window(session, tenant_id=tenant_id)
        window = (start, end, label)
        used = _count_period_whatsapp_sent(session, tenant_id=tenant_id, start=start, end=end)
        limit = plan.whatsapp_msgs_per_month
    else:
        raise ValueError(f"Unsupported plan resource: {kind}")
    if used >= limit:
        if window is not None:
            start, end, label = window
            raise PlanLimitExceededError(
                kind, limit, used=used, period_start=start, period_end=end, period_source=label
            )
        raise PlanLimitExceededError(kind, limit, used=used)
