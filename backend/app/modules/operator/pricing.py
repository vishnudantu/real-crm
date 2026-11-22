"""Computed monthly pricing from the operator's per-tenant feature matrix."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.operator.feature_service import _tenant_or_404, tenant_feature_matrix
from app.modules.operator.features import FEATURE_INDEX
from app.modules.plans.models import Plan


def _pricing_details(session: Session, tenant_id: UUID) -> dict:
    tenant = _tenant_or_404(session, tenant_id)
    plan = session.get(Plan, tenant.plan_id) if tenant.plan_id is not None else None
    plan_features = dict(plan.features or {}) if plan is not None else {}
    matrix = tenant_feature_matrix(session, tenant_id=tenant.id)
    enabled = [row["feature"] for row in matrix if row["enabled"]]
    modules = [
        {
            "feature": key,
            "label": FEATURE_INDEX[key].label,
            "monthly_paise": FEATURE_INDEX[key].monthly_price_paise,
            "bundled_in_plan": plan_features.get(key) is True,
        }
        for key in enabled
    ]
    monthly_paise = sum(row["monthly_paise"] for row in modules)
    addon_paise = sum(
        row["monthly_paise"] for row in modules if not row["bundled_in_plan"]
    )
    plan_base_paise = plan.price_paise if plan is not None else 0
    return {
        "tenant_id": str(tenant.id),
        "enabled": enabled,
        "module_count": len(enabled),
        "monthly_paise": monthly_paise,
        "currency": plan.currency if plan is not None else tenant.currency,
        "modules": modules,
        "plan_base_paise": plan_base_paise,
        "addon_paise": addon_paise,
        "effective_monthly_paise": plan_base_paise + addon_paise,
    }


def compute_tenant_module_total(session: Session, tenant_id: UUID) -> dict:
    """Sum catalog monthly prices for the tenant's effective enabled modules."""

    details = _pricing_details(session, tenant_id)
    return {
        key: details[key]
        for key in ("enabled", "module_count", "monthly_paise", "currency")
    }


def compute_tenant_monthly_pricing(session: Session, tenant_id: UUID) -> dict:
    """Return the plan base plus enabled, unbundled premium module add-ons.

    A module is bundled only when the attached plan's ``features`` map explicitly
    sets it to ``True``. Bundled modules add nothing; other enabled modules add
    their catalog price, including a plan/default-enabled module overridden on.
    With no plan, the base is zero. This is a computed pricing view only: it does
    not alter subscriptions, invoices, or provider billing.
    """

    return _pricing_details(session, tenant_id)
