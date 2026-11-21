"""SaaS operator services: platform identity, tenant provisioning, plans, audit."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.auth.security import (
    hash_password,
    validate_password_strength,
    verify_password,
    verify_password_against_dummy,
)
from app.modules.bookings.models import Booking
from app.modules.leads.models import Lead
from app.modules.messaging.models import MessageDelivery
from app.modules.operator.models import OperatorAuditLog, OperatorUser
from app.modules.tenancy.models import Tenant, TenantStatus
from app.modules.users.models import RoleName, User
from app.modules.users.service import seed_roles


def authenticate_operator(session: Session, *, email: str, password: str) -> OperatorUser | None:
    operator = session.scalar(select(OperatorUser).where(OperatorUser.email == email.strip().lower()))
    if operator is None:
        verify_password_against_dummy(password)
        return None
    if not verify_password(password, operator.password_hash) or not operator.is_active:
        return None
    operator.last_login_at = datetime.now(UTC)
    session.add(operator)
    session.commit()
    return operator


def audit(
    session: Session,
    *,
    operator: OperatorUser,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
) -> OperatorAuditLog:
    row = OperatorAuditLog(
        operator_id=operator.id,
        actor_email=operator.email,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        created_at=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def provision_tenant(session: Session, *, operator: OperatorUser, payload) -> dict:
    """Atomically create tenant + defaults + first ADMIN (operator-only action)."""
    if session.scalar(select(Tenant).where(Tenant.slug == payload.slug)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An organization with this slug already exists.")
    if session.scalar(select(User).where(User.email == str(payload.admin_email).lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")

    seed_roles(session)
    tenant = Tenant(
        slug=payload.slug,
        name=payload.name,
        brand_name=payload.brand_name or payload.name,
        country=payload.country,
        timezone=payload.timezone,
        currency=payload.currency,
        plan_id=payload.plan_id,
    )
    session.add(tenant)
    session.flush()

    from app.modules.users import repository as users_repo
    role = users_repo.get_role_by_name(session, RoleName.ADMIN)
    admin = User(
        tenant_id=tenant.id,
        full_name=payload.admin_full_name,
        email=str(payload.admin_email).lower(),
        password_hash=hash_password(payload.admin_password.get_secret_value()),
        role_id=role.id,
        is_active=True,
    )
    session.add(admin)
    session.flush()

    from app.modules.settings.service import ensure_defaults_seeded
    ensure_defaults_seeded(session, tenant.id)
    audit(
        session,
        operator=operator,
        action="TENANT_PROVISIONED",
        resource_type="TENANT",
        resource_id=str(tenant.id),
        details={"slug": tenant.slug, "admin_email": admin.email, "plan_id": str(payload.plan_id) if payload.plan_id else None},
    )
    session.commit()
    return {"tenant": tenant, "admin": admin}


def tenant_metrics(session: Session, *, tenant_id) -> dict:
    def count(model) -> int:
        return int(session.scalar(select(func.count()).select_from(model).where(model.tenant_id == tenant_id)) or 0)
    return {
        "users": count(User),
        "leads": count(Lead),
        "bookings": count(Booking),
        "deliveries": count(MessageDelivery),
    }


def create_operator(
    session: Session, *, operator: OperatorUser, payload
) -> OperatorUser:
    if session.scalar(select(OperatorUser).where(OperatorUser.email == str(payload.email).lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "An operator with this email already exists.")
    row = OperatorUser(
        email=str(payload.email).lower(),
        full_name=payload.full_name,
        password_hash=hash_password(payload.password.get_secret_value()),
        role=payload.role,
        permissions=payload.permissions,
        is_active=True,
    )
    session.add(row)
    session.flush()
    audit(session, operator=operator, action="OPERATOR_CREATED", resource_type="OPERATOR", resource_id=str(row.id), details={"role": row.role, "email": row.email})
    session.commit()
    session.refresh(row)
    return row


def create_plan(session: Session, *, operator: OperatorUser, payload):
    from app.modules.plans.models import Plan
    if session.scalar(select(Plan).where(Plan.code == payload.code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A plan with this code already exists.")
    row = Plan(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        price_paise=payload.price_paise,
        currency=payload.currency,
        max_users=payload.max_users,
        leads_per_month=payload.leads_per_month,
        whatsapp_msgs_per_month=payload.whatsapp_msgs_per_month,
        features=payload.features,
        is_active=payload.is_active,
    )
    session.add(row)
    session.flush()
    audit(session, operator=operator, action="PLAN_CREATED", resource_type="PLAN", resource_id=str(row.id), details={"code": row.code, "price_paise": row.price_paise})
    session.commit()
    session.refresh(row)
    return row


def update_plan(session: Session, *, operator: OperatorUser, plan_id, payload):
    from app.modules.plans.models import Plan
    row = session.get(Plan, plan_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found.")
    for field in (
        "name", "description", "price_paise", "max_users", "leads_per_month",
        "whatsapp_msgs_per_month", "features", "is_active",
    ):
        if field in payload.model_fields_set:
            value = getattr(payload, field)
            if value is not None:
                setattr(row, field, value)
    row.updated_at = datetime.now(UTC)
    audit(session, operator=operator, action="PLAN_UPDATED", resource_type="PLAN", resource_id=str(row.id), details=payload.model_dump(exclude_unset=True))
    session.commit()
    session.refresh(row)
    return row


def update_tenant_status(session: Session, *, operator: OperatorUser, tenant_id, new_status: TenantStatus) -> Tenant:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found.")
    tenant.status = new_status.value
    tenant.updated_at = datetime.now(UTC)
    # Suspension takes effect immediately: get_current_user rejects non-ACTIVE tenants.
    audit(session, operator=operator, action="TENANT_STATUS_CHANGED", resource_type="TENANT", resource_id=str(tenant_id), details={"status": new_status.value})
    session.commit()
    session.refresh(tenant)
    return tenant


def create_deployment(session: Session, *, operator: OperatorUser, tenant_id, payload):
    from app.modules.operator.deployments import Deployment, DeploymentStatus
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found.")
    now = datetime.now(UTC)
    row = Deployment(
        tenant_id=tenant_id,
        provider=payload.provider,
        environment=payload.environment,
        region=payload.region,
        status=DeploymentStatus.REQUESTED.value,
        deployment_url=payload.api_base_url,
        notes=payload.notes,
        repository_url=payload.repository_url,
        requested_by=operator.id,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    audit(session, operator=operator, action="DEPLOYMENT_REQUESTED", resource_type="DEPLOYMENT", resource_id=str(row.id), details={"tenant_slug": tenant.slug, "provider": row.provider, "environment": row.environment})
    session.commit()
    session.refresh(row)
    return row
