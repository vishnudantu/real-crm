"""Platform feature catalog and per-tenant feature resolution.

Resolution order for a tenant's feature state:

1. Per-tenant override set by an operator (enable/disable).
2. The tenant's subscription plan ``features`` map.
3. The catalog default.

Every feature defaults to disabled unless the catalog says otherwise, so a
new capability never becomes reachable for existing tenants by accident.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.operator.feature_models import TenantFeature


@dataclass(frozen=True)
class FeatureSpec:
    """A controllable product capability."""

    key: str
    label: str
    description: str
    default_enabled: bool = False
    plan_required: bool = False


# Catalog keys are stable strings; never reuse a retired key.
FEATURE_CATALOG: tuple[FeatureSpec, ...] = (
    FeatureSpec(
        "core_leads", "Lead management", "Intake, assignment, and lifecycle of leads",
        default_enabled=True,
    ),
    FeatureSpec(
        "core_visits", "Site visits", "Capacity-controlled site-visit booking",
        default_enabled=True,
    ),
    FeatureSpec(
        "ai_assistant", "AI assistant", "Fact-grounded multilingual buyer chat",
        default_enabled=True,
    ),
    FeatureSpec(
        "omnichannel_inbox", "Omnichannel inbox",
        "One inbox for WhatsApp, Instagram, Messenger and web chat",
    ),
    FeatureSpec(
        "channel_whatsapp", "WhatsApp channel", "Official WhatsApp Cloud API conversation channel",
    ),
    FeatureSpec(
        "channel_instagram", "Instagram channel", "Instagram DM conversation channel",
    ),
    FeatureSpec(
        "channel_messenger", "Facebook Messenger channel", "Messenger conversation channel",
    ),
    FeatureSpec(
        "web_widget", "Website widget", "Embeddable chat bubble and lead-capture form",
        default_enabled=True,
    ),
    FeatureSpec(
        "calling", "Browser calling", "In-app WebRTC calls with recording",
    ),
    FeatureSpec(
        "messaging_triggers", "Messaging automation", "Trigger rules and outbound delivery engine",
        default_enabled=True,
    ),
    FeatureSpec(
        "billing", "Billing", "Razorpay subscriptions and invoices",
    ),
    FeatureSpec(
        "post_sales", "Post-sales pack", "Sale bookings, payment plans, receipts, commissions",
    ),
    FeatureSpec(
        "connectors", "Lead connectors", "Meta Lead Ads and portal email ingestion",
    ),
    FeatureSpec(
        "analytics", "Analytics", "Dashboards, trends, and executive reporting",
        default_enabled=True,
    ),
    FeatureSpec(
        "sla", "SLA timers", "Response targets and breach alarms",
    ),
    FeatureSpec(
        "knowledge_base", "Knowledge base", "Public FAQ and article center",
    ),
    FeatureSpec(
        "csat", "CSAT surveys", "Post-interaction satisfaction collection",
    ),
)

FEATURE_KEYS: frozenset[str] = frozenset(spec.key for spec in FEATURE_CATALOG)
FEATURE_INDEX: dict[str, FeatureSpec] = {spec.key: spec for spec in FEATURE_CATALOG}


def catalog_default(key: str) -> bool:
    spec = FEATURE_INDEX.get(key)
    return bool(spec and spec.default_enabled)


def resolve_features(session: Session, *, tenant_id, plan_features: dict | None) -> dict[str, bool]:
    """Return the effective on/off state for every catalog feature."""

    overrides = {
        row.feature: row.enabled
        for row in session.scalars(
            select(TenantFeature).where(TenantFeature.tenant_id == tenant_id)
        ).all()
    }
    plan_features = plan_features or {}
    resolved: dict[str, bool] = {}
    for key in FEATURE_KEYS:
        if key in overrides:
            resolved[key] = bool(overrides[key])
        elif isinstance(plan_features.get(key), bool):
            resolved[key] = plan_features[key]
        else:
            resolved[key] = catalog_default(key)
    return resolved


def feature_enabled(
    session: Session, *, tenant_id, plan_features: dict | None, key: str
) -> bool:
    """Resolve one feature without materialising the whole catalog."""

    override = session.scalar(
        select(TenantFeature).where(
            TenantFeature.tenant_id == tenant_id, TenantFeature.feature == key
        )
    )
    if override is not None:
        return bool(override.enabled)
    if isinstance((plan_features or {}).get(key), bool):
        return plan_features[key]
    return catalog_default(key)


def tenant_feature_state(session: Session, *, tenant_id, key: str) -> bool:
    """Resolve one feature given only a tenant, loading its plan features."""

    from app.modules.plans.models import Plan
    from app.modules.tenancy.models import Tenant

    plan_features: dict = {}
    tenant = session.get(Tenant, tenant_id)
    if tenant is not None and tenant.plan_id is not None:
        plan = session.get(Plan, tenant.plan_id)
        plan_features = dict(plan.features or {}) if plan else {}
    return feature_enabled(
        session, tenant_id=tenant_id, plan_features=plan_features, key=key
    )
