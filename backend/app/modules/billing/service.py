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
    """Return HTTP 402 Payment Required for an exhausted plan limit."""

    def __init__(self, resource: str, limit: int) -> None:
        super().__init__(
            status.HTTP_402_PAYMENT_REQUIRED,
            {
                "code": "PLAN_LIMIT_EXCEEDED",
                "message": f"Your plan's {resource} limit ({limit}) has been reached. Upgrade to continue.",
            },
        )


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


def summary(session: Session, *, tenant_id: UUID) -> dict:
    """Return plan, subscription, usage, and recent invoices for the tenant."""

    plan = current_plan(session, tenant_id=tenant_id)
    subscription = session.scalar(
        select(Subscription)
        .where(Subscription.tenant_id == tenant_id)
        .order_by(Subscription.created_at.desc())
    )
    usage = {
        "users": session.scalar(select(func.count(User.id)).where(User.tenant_id == tenant_id)) or 0,
        "leads": session.scalar(select(func.count(Lead.id)).where(Lead.tenant_id == tenant_id)) or 0,
        "whatsapp_sent": session.scalar(
            select(func.count(MessageDelivery.id)).where(
                MessageDelivery.tenant_id == tenant_id,
                MessageDelivery.channel == "WHATSAPP",
                MessageDelivery.status == "SENT",
            )
        ) or 0,
    }
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
    """Reject user/lead/WhatsApp creation when the tenant's plan limit is reached."""

    plan = current_plan(session, tenant_id=tenant_id)
    if plan is None:
        return  # No plan = ungated development tenant.

    if kind == "users":
        used = session.scalar(select(func.count(User.id)).where(User.tenant_id == tenant_id)) or 0
        limit = plan.max_users
    elif kind == "leads":
        used = session.scalar(select(func.count(Lead.id)).where(Lead.tenant_id == tenant_id)) or 0
        limit = plan.leads_per_month
    elif kind == "whatsapp":
        used = session.scalar(
            select(func.count(MessageDelivery.id)).where(
                MessageDelivery.tenant_id == tenant_id,
                MessageDelivery.channel == "WHATSAPP",
                MessageDelivery.status == "SENT",
            )
        ) or 0
        limit = plan.whatsapp_msgs_per_month
    else:
        raise ValueError(f"Unsupported plan resource: {kind}")
    if used >= limit:
        raise PlanLimitExceededError(kind, limit)
