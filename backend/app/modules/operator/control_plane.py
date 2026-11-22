"""Tenant control-plane: config, usage, health, impersonation, bulk features.

Aggregates read-only views and operator mutations for a single tenant. These
functions are used by the operator router; they never touch ciphertext or API
keys, only metadata and counts.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.billing.models import SubscriptionStatus
from app.modules.billing.service import (
    _count_active_users,
    _count_period_leads,
    _count_period_whatsapp_sent,
    _current_usage_window,
    _latest_subscription,
    current_plan,
)
from app.modules.bookings.models import Booking
from app.modules.leads.models import Lead
from app.modules.messaging.models import MessageDelivery
from app.modules.omnichannel.models import ChannelConversation, ChannelCredential
from app.modules.operator import features as features_mod
from app.modules.operator.feature_service import set_feature, tenant_feature_matrix
from app.modules.operator.models import OperatorUser
from app.modules.operator.service import audit
from app.modules.plans.models import Plan
from app.modules.projects.models import Project
from app.modules.settings.models import SystemSetting
from app.modules.tenancy.models import Tenant, TenantStatus
from app.modules.users.models import RoleName, User


def _tenant_or_404(session: Session, tenant_id: UUID) -> Tenant:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found.")
    return tenant


def _count(session: Session, model, tenant_id: UUID, *extra) -> int:
    stmt = select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
    for clause in extra:
        stmt = stmt.where(clause)
    return int(session.scalar(stmt) or 0)


# ---------------------------------------------------------------------------
# Config read
# ---------------------------------------------------------------------------


def tenant_config(session: Session, *, tenant_id: UUID) -> dict:
    tenant = _tenant_or_404(session, tenant_id)
    plan = current_plan(session, tenant_id=tenant_id)
    plan_summary = None
    if plan is not None:
        plan_summary = {
            "id": plan.id, "code": plan.code, "name": plan.name, "price_paise": plan.price_paise,
        }

    channels = list(
        session.scalars(
            select(ChannelCredential).where(ChannelCredential.tenant_id == tenant_id)
        ).all()
    )
    channel_rows = [
        {
            "channel": c.channel,
            "provider": c.provider,
            "is_active": c.is_active,
            "updated_at": c.updated_at,
        }
        for c in channels
    ]

    ai = _ai_summary(session, tenant_id=tenant_id)

    matrix = tenant_feature_matrix(session, tenant_id=tenant_id)
    enabled_count = sum(1 for row in matrix if row["enabled"])

    widget_enabled = any(
        row["feature"] == "web_widget" and row["enabled"] for row in matrix
    )
    embed_url = f"/api/v1/widget/{tenant.slug}/embed.js" if widget_enabled else None

    counts = {
        "users": _count(session, User, tenant_id),
        "active_users": _count_active_users(session, tenant_id=tenant_id),
        "leads_total": _count(session, Lead, tenant_id),
        "projects": _count(session, Project, tenant_id),
        "bookings": _count(session, Booking, tenant_id),
        "open_conversations": _count(
            session, ChannelConversation, tenant_id,
            ChannelConversation.status == "OPEN",
        ),
    }

    return {
        "id": tenant.id,
        "slug": tenant.slug,
        "name": tenant.name,
        "status": tenant.status,
        "country": tenant.country,
        "timezone": tenant.timezone,
        "currency": tenant.currency,
        "plan": plan_summary,
        "branding": {
            "brand_name": tenant.brand_name,
            "logo_path": tenant.logo_path,
            "theme_json": tenant.theme_json,
        },
        "widget": {"enabled": widget_enabled, "embed_url": embed_url},
        "channels": channel_rows,
        "ai": ai,
        "features": {"enabled_count": enabled_count, "total_count": len(matrix)},
        "counts": counts,
    }


def _ai_summary(session: Session, *, tenant_id: UUID) -> dict:
    """Return provider/model names and whether a key is configured — never keys."""
    settings = get_settings()
    row = session.get(SystemSetting, (tenant_id, "ai_assistant"))
    override = (row.value if row else {}) or {}
    provider = override.get("provider") or settings.ai_provider or "groq"
    if provider == "groq":
        model = override.get("model") or settings.groq_model
        configured = bool(settings.groq_api_key) or bool(override.get("api_key"))
    else:
        model = override.get("model") or settings.ai_model
        configured = bool(settings.ai_api_key) or bool(override.get("api_key"))
    return {"provider": provider, "model": model, "configured": configured}


# ---------------------------------------------------------------------------
# Config patch
# ---------------------------------------------------------------------------

_AUDIT_DETAIL_CAP = 200


def _cap(value):
    """Cap audit detail values so theme blobs never flood the audit log."""
    text = json.dumps(value, default=str)
    if len(text) <= _AUDIT_DETAIL_CAP:
        return value
    return {"_truncated": True, "keys": sorted(value.keys()) if isinstance(value, dict) else None}


def update_tenant_config(
    session: Session, *, operator: OperatorUser, tenant_id: UUID, payload
) -> Tenant:
    tenant = _tenant_or_404(session, tenant_id)
    changes: dict = {}
    fields = payload.model_fields_set

    if "brand_name" in fields and payload.brand_name is not None:
        if tenant.brand_name != payload.brand_name:
            changes["brand_name"] = {"before": tenant.brand_name, "after": payload.brand_name}
            tenant.brand_name = payload.brand_name
    if "timezone" in fields and payload.timezone is not None:
        if tenant.timezone != payload.timezone:
            changes["timezone"] = {"before": tenant.timezone, "after": payload.timezone}
            tenant.timezone = payload.timezone
    if "currency" in fields and payload.currency is not None:
        if tenant.currency != payload.currency:
            changes["currency"] = {"before": tenant.currency, "after": payload.currency}
            tenant.currency = payload.currency
    if "country" in fields and payload.country is not None:
        if tenant.country != payload.country:
            changes["country"] = {"before": tenant.country, "after": payload.country}
            tenant.country = payload.country
    if "theme_json" in fields and payload.theme_json is not None:
        merged = {**(tenant.theme_json or {}), **payload.theme_json}
        if merged != (tenant.theme_json or {}):
            changes["theme_json"] = {
                "before": _cap(tenant.theme_json or {}),
                "after": _cap(merged),
            }
            tenant.theme_json = merged

    if changes:
        tenant.updated_at = datetime.now(UTC)
        audit(
            session,
            operator=operator,
            action="TENANT_CONFIG_UPDATED",
            resource_type="TENANT",
            resource_id=str(tenant_id),
            details={"slug": tenant.slug, "changed_fields": changes},
        )
    session.commit()
    session.refresh(tenant)
    return tenant


# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------


def tenant_usage(session: Session, *, tenant_id: UUID, days: int = 30) -> dict:
    _tenant_or_404(session, tenant_id)
    plan = current_plan(session, tenant_id=tenant_id)
    start, end, label = _current_usage_window(session, tenant_id=tenant_id)

    meters = {
        "leads": {
            "used": _count_period_leads(session, tenant_id=tenant_id, start=start, end=end),
            "limit": plan.leads_per_month if plan else None,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "period_source": label,
        },
        "messages": {
            "used": _count_period_whatsapp_sent(session, tenant_id=tenant_id, start=start, end=end),
            "limit": plan.whatsapp_msgs_per_month if plan else None,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "period_source": label,
        },
        "users": {
            "used": _count_active_users(session, tenant_id=tenant_id),
            "limit": plan.max_users if plan else None,
            "period_start": None,
            "period_end": None,
            "period_source": None,
        },
    }

    lifetime = {
        "leads_total": _count(session, Lead, tenant_id),
        "bookings_total": _count(session, Booking, tenant_id),
        "messages_sent_total": _count(
            session, MessageDelivery, tenant_id,
            MessageDelivery.status == "SENT",
        ),
        "active_users": _count_active_users(session, tenant_id=tenant_id),
        "channels_active": _count(
            session, ChannelCredential, tenant_id,
            ChannelCredential.is_active.is_(True),
        ),
    }

    series = _daily_series(session, tenant_id=tenant_id, days=days)

    return {"days": days, "meters": meters, **lifetime, "series": series}


def _daily_series(session: Session, *, tenant_id: UUID, days: int) -> list[dict]:
    """Return [{date, leads, messages_sent}] for the trailing N days (UTC dates)."""
    now = datetime.now(UTC)
    since = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    lead_rows = session.execute(
        select(func.date(Lead.created_at).label("d"), func.count(Lead.id).label("n"))
        .where(Lead.tenant_id == tenant_id, Lead.created_at >= since)
        .group_by(func.date(Lead.created_at))
    ).all()
    occurred = func.coalesce(MessageDelivery.sent_at, MessageDelivery.created_at)
    msg_rows = session.execute(
        select(func.date(occurred).label("d"), func.count(MessageDelivery.id).label("n"))
        .where(
            MessageDelivery.tenant_id == tenant_id,
            MessageDelivery.status == "SENT",
            occurred >= since,
        )
        .group_by(func.date(occurred))
    ).all()

    lead_map = {str(r.d): int(r.n) for r in lead_rows}
    msg_map = {str(r.d): int(r.n) for r in msg_rows}

    series = []
    for offset in range(days):
        day = (since + timedelta(days=offset)).date().isoformat()
        series.append({
            "date": day,
            "leads": lead_map.get(day, 0),
            "messages_sent": msg_map.get(day, 0),
        })
    return series


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

_RECENT_ACTIVITY_DAYS = 14


def tenant_health(session: Session, *, tenant_id: UUID) -> dict:
    tenant = _tenant_or_404(session, tenant_id)
    checks: list[dict] = []

    active = tenant.status == TenantStatus.ACTIVE.value
    checks.append({
        "name": "tenant_active",
        "state": "green" if active else "red",
        "detail": f"Tenant status is {tenant.status}.",
    })

    checks.append(_plan_check(session, tenant_id=tenant_id))

    matrix = tenant_feature_matrix(session, tenant_id=tenant_id)
    widget_on = any(r["feature"] == "web_widget" and r["enabled"] for r in matrix)
    checks.append({
        "name": "widget_enabled",
        "state": "green" if widget_on else "yellow",
        "detail": "Website widget is enabled." if widget_on else "Website widget is disabled.",
    })

    channels = _count(
        session, ChannelCredential, tenant_id, ChannelCredential.is_active.is_(True)
    )
    checks.append({
        "name": "channels_configured",
        "state": "green" if channels > 0 else "yellow",
        "detail": f"{channels} active channel credential(s).",
    })

    ai = _ai_summary(session, tenant_id=tenant_id)
    checks.append({
        "name": "ai_configured",
        "state": "green" if ai["configured"] else "yellow",
        "detail": f"Provider {ai['provider']} key {'present' if ai['configured'] else 'missing'}.",
    })

    recent = _has_recent_activity(session, tenant_id=tenant_id)
    checks.append({
        "name": "recent_activity",
        "state": "green" if recent else "yellow",
        "detail": (
            f"Activity within {_RECENT_ACTIVITY_DAYS} days." if recent
            else f"No lead/delivery/message in the last {_RECENT_ACTIVITY_DAYS} days."
        ),
    })

    rank = {"green": 0, "yellow": 1, "red": 2}
    overall = max((c["state"] for c in checks), key=lambda s: rank[s])
    return {"tenant_id": tenant_id, "overall": overall, "checks": checks}


def _plan_check(session: Session, *, tenant_id: UUID) -> dict:
    subscription = _latest_subscription(session, tenant_id=tenant_id)
    if subscription is None:
        plan = current_plan(session, tenant_id=tenant_id)
        if plan is not None:
            return {
                "name": "plan_current",
                "state": "green",
                "detail": f"Plan {plan.code} attached without subscription.",
            }
        return {"name": "plan_current", "state": "yellow", "detail": "No plan or subscription."}
    if subscription.status == SubscriptionStatus.ACTIVE.value:
        return {
            "name": "plan_current",
            "state": "green",
            "detail": f"Subscription {subscription.status}, period ends {subscription.current_period_end}.",
        }
    if subscription.status in (SubscriptionStatus.PAST_DUE.value, SubscriptionStatus.HALTED.value):
        return {
            "name": "plan_current",
            "state": "yellow",
            "detail": f"Subscription {subscription.status}.",
        }
    return {
        "name": "plan_current",
        "state": "red",
        "detail": f"Subscription {subscription.status}.",
    }


def _has_recent_activity(session: Session, *, tenant_id: UUID) -> bool:
    cutoff = datetime.now(UTC) - timedelta(days=_RECENT_ACTIVITY_DAYS)
    lead = session.scalar(
        select(func.count(Lead.id)).where(Lead.tenant_id == tenant_id, Lead.created_at >= cutoff)
    )
    if lead:
        return True
    delivery = session.scalar(
        select(func.count(MessageDelivery.id)).where(
            MessageDelivery.tenant_id == tenant_id, MessageDelivery.created_at >= cutoff
        )
    )
    if delivery:
        return True
    return False


# ---------------------------------------------------------------------------
# Impersonation
# ---------------------------------------------------------------------------

IMPERSONATION_EXPIRES_SECONDS = 900


def impersonate_tenant(
    session: Session, *, operator: OperatorUser, tenant_id: UUID, settings: Settings | None = None
) -> dict:
    config = settings or get_settings()
    tenant = _tenant_or_404(session, tenant_id)
    if tenant.status != TenantStatus.ACTIVE.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only ACTIVE tenants can be impersonated.")

    admin = session.scalar(
        select(User)
        .join(User.role)
        .where(User.tenant_id == tenant_id, User.is_active.is_(True))
        .where(User.role.has(name=RoleName.ADMIN.value))
        .order_by(User.created_at.asc())
    )
    if admin is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active ADMIN user for this tenant.")

    issued_at = datetime.now(UTC)
    payload = {
        "sub": str(admin.id),
        "role": admin.role.name,
        "type": "access",
        "jti": str(uuid4()),
        "iat": issued_at,
        "exp": issued_at + timedelta(seconds=IMPERSONATION_EXPIRES_SECONDS),
        "iss": config.jwt_issuer,
        "aud": config.jwt_audience,
        "tenant_id": str(tenant.id),
        "security_version": admin.security_version,
        "impersonated_by": str(operator.id),
    }
    token = jwt.encode(
        payload,
        config.jwt_secret_key.get_secret_value(),
        algorithm=config.jwt_algorithm,
    )

    audit(
        session,
        operator=operator,
        action="IMPERSONATION_STARTED",
        resource_type="TENANT",
        resource_id=str(tenant.id),
        details={
            "slug": tenant.slug,
            "target_user_id": str(admin.id),
            "target_email": admin.email,
            "impersonated_by": str(operator.id),
        },
    )
    session.commit()

    return {
        "access_token": token,
        "expires_in": IMPERSONATION_EXPIRES_SECONDS,
        "user": {
            "id": admin.id,
            "email": admin.email,
            "full_name": admin.full_name,
            "role": admin.role.name,
        },
    }


# ---------------------------------------------------------------------------
# Bulk features
# ---------------------------------------------------------------------------


def bulk_set_features(
    session: Session, *, operator: OperatorUser, tenant_id: UUID, features_map: dict[str, bool]
) -> list[dict]:
    _tenant_or_404(session, tenant_id)
    unknown = sorted(k for k in features_map if k not in features_mod.FEATURE_KEYS)
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"message": "Unknown feature keys.", "unknown": unknown},
        )
    for key, enabled in features_map.items():
        set_feature(
            session, operator=operator, tenant_id=tenant_id,
            feature=key, enabled=enabled, reason="Bulk operator update",
        )
    return tenant_feature_matrix(session, tenant_id=tenant_id)
