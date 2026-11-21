"""Tenant signup, branding, and settings API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser, CurrentUser
from app.modules.auth.schemas import TokenResponse
from app.modules.tenancy.exceptions import TenantNotFoundError
from app.modules.tenancy.models import Tenant, TenantStatus
from app.modules.tenancy.schemas import (
    TenantSettingsResponse,
    TenantSettingsUpdateRequest,
    TenantSignupRequest,
)
from app.modules.tenancy.service import (
    signup_tenant,
    tenant_settings,
    update_tenant_settings,
)

router = APIRouter(prefix="/tenancy", tags=["tenancy"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(
    payload: TenantSignupRequest,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    result = signup_tenant(
        db,
        name=payload.name,
        slug=payload.slug,
        full_name=payload.full_name,
        email=str(payload.email),
        password=payload.password.get_secret_value(),
        settings=settings,
    )
    return TokenResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        refresh_token=result.refresh_token,
        refresh_expires_in=result.refresh_expires_in,
    )


@router.get("/settings", response_model=TenantSettingsResponse)
def get_settings_endpoint(
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
) -> TenantSettingsResponse:
    tenant = db.get(Tenant, current_user.tenant_id)
    return tenant_settings(db, tenant)


@router.put("/settings", response_model=TenantSettingsResponse)
def put_settings_endpoint(
    payload: TenantSettingsUpdateRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> TenantSettingsResponse:
    tenant = db.get(Tenant, admin.tenant_id)
    return update_tenant_settings(
        db,
        tenant=tenant,
        brand_name=payload.brand_name,
        logo_path=payload.logo_path,
        clear_logo="logo_path" in payload.model_fields_set and payload.logo_path is None,
        theme=payload.theme,
        currency=payload.currency,
        timezone=payload.timezone,
        date_format=payload.date_format,
    )


@router.get("/public/{slug}", response_model=TenantSettingsResponse)
def public_settings_endpoint(
    slug: str,
    db: Annotated[Session, Depends(get_db)],
) -> TenantSettingsResponse:
    tenant = db.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant is None or tenant.status != TenantStatus.ACTIVE.value:
        raise TenantNotFoundError()
    return tenant_settings(db, tenant)
