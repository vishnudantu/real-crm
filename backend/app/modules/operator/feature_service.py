"""Operator actions for per-tenant feature control."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.operator import features
from app.modules.operator.feature_models import TenantFeature
from app.modules.operator.models import OperatorAuditLog, OperatorUser
from app.modules.operator.service import audit
from app.modules.plans.models import Plan
from app.modules.tenancy.models import Tenant


def _tenant_or_404(session: Session, tenant_id) -> Tenant:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found.")
    return tenant


def _plan_features(session: Session, tenant: Tenant) -> dict:
    if tenant.plan_id is None:
        return {}
    plan = session.get(Plan, tenant.plan_id)
    return dict(plan.features or {}) if plan else {}


def tenant_feature_matrix(session: Session, *, tenant_id) -> list[dict]:
    """Full catalog with effective state and the source of each decision."""

    tenant = _tenant_or_404(session, tenant_id)
    plan_features = _plan_features(session, tenant)
    overrides = {
        row.feature: row
        for row in session.scalars(
            select(TenantFeature).where(TenantFeature.tenant_id == tenant.id)
        ).all()
    }
    rows: list[dict] = []
    for spec in sorted(features.FEATURE_CATALOG, key=lambda s: s.key):
        override = overrides.get(spec.key)
        if override is not None:
            enabled, source = bool(override.enabled), "TENANT_OVERRIDE"
        elif isinstance(plan_features.get(spec.key), bool):
            enabled, source = plan_features[spec.key], "PLAN"
        else:
            enabled, source = spec.default_enabled, "CATALOG_DEFAULT"
        rows.append(
            {
                "feature": spec.key,
                "label": spec.label,
                "description": spec.description,
                "enabled": enabled,
                "source": source,
                "reason": override.reason if override else None,
                "updated_at": override.updated_at.isoformat() if override else None,
            }
        )
    return rows


def set_feature(
    session: Session,
    *,
    operator: OperatorUser,
    tenant_id,
    feature: str,
    enabled: bool,
    reason: str | None = None,
) -> dict:
    if feature not in features.FEATURE_KEYS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown feature: {feature}")
    tenant = _tenant_or_404(session, tenant_id)
    row = session.scalar(
        select(TenantFeature).where(
            TenantFeature.tenant_id == tenant.id, TenantFeature.feature == feature
        )
    )
    if row is None:
        row = TenantFeature(tenant_id=tenant.id, feature=feature)
        session.add(row)
    row.enabled = enabled
    row.reason = reason
    row.set_by_email = operator.email
    row.updated_at = datetime.now(UTC)
    audit(
        session,
        operator=operator,
        action="FEATURE_ENABLED" if enabled else "FEATURE_DISABLED",
        resource_type="TENANT_FEATURE",
        resource_id=f"{tenant.slug}:{feature}",
        details={"enabled": enabled, "reason": reason},
    )
    session.commit()
    return {
        "feature": feature,
        "tenant_id": str(tenant.id),
        "enabled": enabled,
        "source": "TENANT_OVERRIDE",
    }


def reset_feature(session: Session, *, operator: OperatorUser, tenant_id, feature: str) -> dict:
    """Remove the override so plan/default governs the feature again."""

    if feature not in features.FEATURE_KEYS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown feature: {feature}")
    tenant = _tenant_or_404(session, tenant_id)
    deleted = session.query(TenantFeature).filter(
        TenantFeature.tenant_id == tenant.id, TenantFeature.feature == feature
    ).delete()
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No override exists for this feature.")
    audit(
        session,
        operator=operator,
        action="FEATURE_RESET",
        resource_type="TENANT_FEATURE",
        resource_id=f"{tenant.slug}:{feature}",
        details={},
    )
    session.commit()
    return {"feature": feature, "tenant_id": str(tenant.id), "source": "OVERRIDE_REMOVED"}
