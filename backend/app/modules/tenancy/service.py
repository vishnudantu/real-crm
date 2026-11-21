"""Tenant provisioning services."""

from __future__ import annotations

from typing import TYPE_CHECKING
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.security import hash_password

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.modules.auth.service import LoginResult
from app.modules.tenancy.models import Tenant

DEFAULT_TENANT_SLUG = "default"


def get_or_create_tenant(session: Session, *, slug: str = DEFAULT_TENANT_SLUG) -> Tenant:
    """Resolve the configured development organization, creating it if needed."""

    tenant = session.scalar(select(Tenant).where(Tenant.slug == slug))
    if tenant is None:
        tenant = Tenant(slug=slug, name="Default Tenant")
        session.add(tenant)
        session.flush()
    return tenant


def tenant_settings(session: Session, tenant: Tenant | None) -> "TenantSettingsResponse":
    from app.modules.tenancy.exceptions import TenantNotFoundError

    if tenant is None:
        raise TenantNotFoundError()
    from app.modules.tenancy.schemas import TenantSettingsResponse, TenantTheme

    theme = TenantTheme(**(tenant.theme_json or {}))
    return TenantSettingsResponse(
        slug=tenant.slug,
        brand_name=tenant.brand_name,
        logo_path=tenant.logo_path,
        theme=theme,
        currency=tenant.currency,
        timezone=tenant.timezone,
        date_format=(tenant.theme_json or {}).get("date_format", "DD/MM/YYYY"),
    )


def update_tenant_settings(
    session: Session,
    *,
    tenant: Tenant | None,
    brand_name: str | None = None,
    logo_path: str | None = None,
    clear_logo: bool = False,
    theme=None,
    currency: str | None = None,
    timezone: str | None = None,
    date_format: str | None = None,
) -> "TenantSettingsResponse":
    from app.modules.tenancy.exceptions import TenantNotFoundError

    if tenant is None:
        raise TenantNotFoundError()
    if brand_name is not None:
        tenant.brand_name = brand_name
    if clear_logo:
        tenant.logo_path = None
    elif logo_path is not None:
        tenant.logo_path = logo_path
    if currency is not None:
        tenant.currency = currency
    if timezone is not None:
        tenant.timezone = timezone
    merged = dict(tenant.theme_json or {})
    if theme is not None:
        merged.update(theme.model_dump(exclude_unset=True))
    if date_format is not None:
        merged["date_format"] = date_format
    tenant.theme_json = merged
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant_settings(session, tenant)


def signup_tenant(
    session: Session,
    *,
    name: str,
    slug: str,
    full_name: str,
    email: str,
    password: str,
    settings: Settings,
) -> LoginResult:
    """Create a tenant and its first administrator in one transaction."""

    from app.modules.auth.service import login_user
    from app.modules.users import repository
    from app.modules.users.service import seed_roles
    from app.modules.auth.exceptions import EmailAlreadyRegisteredError
    from app.modules.tenancy.exceptions import TenantSlugAlreadyExistsError
    from app.modules.users.models import RoleName, User

    if session.scalar(select(Tenant).where(Tenant.slug == slug)) is not None:
        raise TenantSlugAlreadyExistsError()
    if repository.get_user_by_email(session, email) is not None:
        raise EmailAlreadyRegisteredError()

    seed_roles(session)
    tenant = Tenant(slug=slug, name=name)
    session.add(tenant)
    session.flush()
    role = repository.get_role_by_name(session, RoleName.ADMIN)
    user = User(
        tenant_id=tenant.id,
        full_name=full_name,
        email=email.strip().lower(),
        password_hash=hash_password(password),
        role_id=role.id,
        is_active=True,
    )
    session.add(user)
    session.commit()
    return login_user(session, email=email, password=password, settings=settings)
