"""Operator-only control-plane API (no tenant-role dependency)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.operator import feature_service, features, service
from app.modules.operator.dependencies import (
    CurrentOperator,
    get_current_operator,
    require_operator_permission,
)
from app.modules.operator.models import OperatorAuditLog, OperatorPermission, OperatorUser
from app.modules.operator.schemas import (
    OperatorAuditLogResponse,
    OperatorCreateRequest,
    OperatorLoginRequest,
    OperatorTokenResponse,
    OperatorUpdateRequest,
    OperatorUserResponse,
    PlanCreateRequest,
    PlanResponse,
    PlanUpdateRequest,
    TenantCreateRequest,
    TenantDeploymentRequest,
    TenantDeploymentResponse,
    TenantFeatureEntry,
    TenantFeatureUpdateRequest,
    TenantOnboardRequest,
    TenantProvisionResponse,
    TenantStatusUpdateRequest,
)
from app.modules.operator.security import create_operator_token
from app.modules.plans.models import Plan
from app.modules.tenancy.models import Tenant

router = APIRouter(prefix="/operator", tags=["operator"])


@router.post("/auth/login", response_model=OperatorTokenResponse)
def login(
    payload: OperatorLoginRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    operator = service.authenticate_operator(
        db, email=str(payload.email), password=payload.password.get_secret_value()
    )
    if operator is None:
        from fastapi import HTTPException
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid operator credentials.")
    return OperatorTokenResponse(
        access_token=create_operator_token(operator, settings=settings),
        expires_in=settings.operator_token_expire_minutes * 60,
    )


@router.get("/auth/me", response_model=OperatorUserResponse)
def me(operator: CurrentOperator):
    return operator


@router.get("/operators", response_model=list[OperatorUserResponse])
def list_operators(
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.OPERATORS_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    return list(db.scalars(select(OperatorUser).order_by(OperatorUser.created_at.desc())).all())


@router.post("/operators", response_model=OperatorUserResponse, status_code=status.HTTP_201_CREATED)
def create_operator(
    payload: OperatorCreateRequest,
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.OPERATORS_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    return service.create_operator(db, operator=operator, payload=payload)


@router.patch("/operators/{operator_id}", response_model=OperatorUserResponse)
def update_operator(
    operator_id: UUID,
    payload: OperatorUpdateRequest,
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.OPERATORS_MANAGE))],
    db: Annotated[Session, Depends(get_db)],
):
    target = db.get(OperatorUser, operator_id)
    if target is None:
        from fastapi import HTTPException
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Operator not found.")
    fields = payload.model_fields_set
    if "role" in fields and payload.role is not None:
        target.role = payload.role
    if "permissions" in fields and payload.permissions is not None:
        target.permissions = payload.permissions
    if "is_active" in fields and payload.is_active is not None:
        target.is_active = payload.is_active
    service.audit(
        db, operator=operator, action="OPERATOR_UPDATED", resource_type="OPERATOR",
        resource_id=str(operator_id), details=payload.model_dump(exclude_unset=True),
    )
    db.commit()
    db.refresh(target)
    return target


@router.get("/tenants")
def list_tenants(
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.TENANTS_READ))],
    db: Annotated[Session, Depends(get_db)],
):
    rows = db.scalars(select(Tenant).order_by(Tenant.created_at.desc())).all()
    return [
        {
            "id": row.id,
            "slug": row.slug,
            "name": row.name,
            "brand_name": row.brand_name,
            "status": row.status,
            "plan_id": row.plan_id,
            "country": row.country,
            "timezone": row.timezone,
            "currency": row.currency,
            **service.tenant_metrics(db, tenant_id=row.id),
        }
        for row in rows
    ]


@router.post("/tenants", response_model=TenantProvisionResponse, status_code=status.HTTP_201_CREATED)
def provision_tenant(
    payload: TenantCreateRequest,
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.TENANTS_WRITE))],
    db: Annotated[Session, Depends(get_db)],
):
    result = service.provision_tenant(db, operator=operator, payload=payload)
    tenant = result["tenant"]
    admin = result["admin"]
    return TenantProvisionResponse(
        id=tenant.id,
        slug=tenant.slug,
        name=tenant.name,
        brand_name=tenant.brand_name,
        status=tenant.status,
        plan_id=tenant.plan_id,
        admin_user_id=admin.id,
        admin_email=admin.email,
    )


@router.get("/tenants/{tenant_id}")
def tenant_detail(
    tenant_id: UUID,
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.TENANTS_READ))],
    db: Annotated[Session, Depends(get_db)],
):
    from fastapi import HTTPException
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found.")
    return {
        "id": tenant.id,
        "slug": tenant.slug,
        "name": tenant.name,
        "brand_name": tenant.brand_name,
        "status": tenant.status,
        "plan_id": tenant.plan_id,
        "theme_json": tenant.theme_json,
        "country": tenant.country,
        "timezone": tenant.timezone,
        "currency": tenant.currency,
        **service.tenant_metrics(db, tenant_id=tenant.id),
    }


@router.patch("/tenants/{tenant_id}/status")
def update_tenant_status(
    tenant_id: UUID,
    payload: TenantStatusUpdateRequest,
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.TENANTS_WRITE))],
    db: Annotated[Session, Depends(get_db)],
):
    tenant = service.update_tenant_status(db, operator=operator, tenant_id=tenant_id, new_status=payload.status)
    return {"id": tenant.id, "slug": tenant.slug, "status": tenant.status}


@router.get("/plans", response_model=list[PlanResponse])
def list_plans(
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.TENANTS_READ))],
    db: Annotated[Session, Depends(get_db)],
):
    return list(db.scalars(select(Plan).order_by(Plan.price_paise)).all())


@router.post("/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: PlanCreateRequest,
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.PLANS_WRITE))],
    db: Annotated[Session, Depends(get_db)],
):
    return service.create_plan(db, operator=operator, payload=payload)


@router.patch("/plans/{plan_id}", response_model=PlanResponse)
def update_plan(
    plan_id: UUID,
    payload: PlanUpdateRequest,
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.PLANS_WRITE))],
    db: Annotated[Session, Depends(get_db)],
):
    return service.update_plan(db, operator=operator, plan_id=plan_id, payload=payload)


@router.post("/tenants/{tenant_id}/deployments", response_model=TenantDeploymentResponse, status_code=status.HTTP_201_CREATED)
def request_deployment(
    tenant_id: UUID,
    payload: TenantDeploymentRequest,
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.DEPLOYMENTS_WRITE))],
    db: Annotated[Session, Depends(get_db)],
):
    return service.create_deployment(db, operator=operator, tenant_id=tenant_id, payload=payload)


@router.get("/audit-logs", response_model=list[OperatorAuditLogResponse])
def audit_logs(
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.AUDIT_READ))],
    db: Annotated[Session, Depends(get_db)],
):
    return list(db.scalars(select(OperatorAuditLog).order_by(OperatorAuditLog.created_at.desc()).limit(200)).all())


@router.get("/features/catalog")
def feature_catalog(
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.TENANTS_READ))],
):
    """Every controllable capability and whether it is on by default."""

    return [
        {
            "feature": spec.key,
            "label": spec.label,
            "description": spec.description,
            "default_enabled": spec.default_enabled,
        }
        for spec in sorted(features.FEATURE_CATALOG, key=lambda s: s.key)
    ]


@router.get("/tenants/{tenant_id}/features", response_model=list[TenantFeatureEntry])
def tenant_features(
    tenant_id: UUID,
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.TENANTS_READ))],
    db: Annotated[Session, Depends(get_db)],
):
    return feature_service.tenant_feature_matrix(db, tenant_id=tenant_id)


@router.put("/tenants/{tenant_id}/features/{feature}")
def enable_or_disable_feature(
    tenant_id: UUID,
    feature: str,
    payload: TenantFeatureUpdateRequest,
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.TENANTS_WRITE))],
    db: Annotated[Session, Depends(get_db)],
):
    """Explicitly enable or disable one feature for one tenant (audited)."""

    return feature_service.set_feature(
        db,
        operator=operator,
        tenant_id=tenant_id,
        feature=feature,
        enabled=payload.enabled,
        reason=payload.reason,
    )


@router.delete("/tenants/{tenant_id}/features/{feature}")
def reset_feature(
    tenant_id: UUID,
    feature: str,
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.TENANTS_WRITE))],
    db: Annotated[Session, Depends(get_db)],
):
    """Remove the per-tenant override and fall back to the plan/default."""

    return feature_service.reset_feature(db, operator=operator, tenant_id=tenant_id, feature=feature)


@router.post("/tenants/onboard", status_code=status.HTTP_201_CREATED)
def onboard_tenant(
    payload: TenantOnboardRequest,
    operator: Annotated[OperatorUser, Depends(require_operator_permission(OperatorPermission.TENANTS_WRITE))],
    db: Annotated[Session, Depends(get_db)],
):
    """One-step onboarding wizard: provision tenant, plan, and starter flags."""

    from fastapi import HTTPException

    plan_id = payload.plan_id
    if payload.plan_code:
        from sqlalchemy import select as sql_select

        plan = db.scalar(sql_select(Plan).where(Plan.code == payload.plan_code, Plan.is_active.is_(True)))
        if plan is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"No active plan named {payload.plan_code!r}.")
        plan_id = plan.id
    base_payload = payload.model_copy(update={"plan_id": plan_id})
    result = service.provision_tenant(db, operator=operator, payload=base_payload)
    tenant = result["tenant"]
    requested_flags = {
        "omnichannel_inbox": payload.enable_omnichannel,
        "channel_whatsapp": payload.enable_omnichannel,
        "calling": payload.enable_calling,
        "connectors": payload.enable_connectors,
        "post_sales": payload.enable_post_sales,
    }
    for feature_key, enabled in requested_flags.items():
        if enabled:
            feature_service.set_feature(
                db, operator=operator, tenant_id=tenant.id, feature=feature_key, enabled=True,
                reason="Onboarding wizard selection",
            )
    embed_url = None
    if payload.enable_omnichannel or payload.embed_url is not None:
        embed_url = f"/api/v1/widget/{tenant.slug}/embed.js"
    return {
        "tenant_id": tenant.id,
        "slug": tenant.slug,
        "brand_name": tenant.brand_name,
        "status": tenant.status,
        "plan_id": plan_id,
        "admin_email": result["admin"].email,
        "embed_script_url": embed_url,
        "enabled_features": [k for k, v in requested_flags.items() if v],
    }
