"""Tenant context and write-isolation unit tests."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from uuid import uuid4

from app.db.base import Base
from app.db.tenancy import TenantContext, require_tenant_context, with_tenant
from app.modules.tenancy.models import Tenant, TenantStatus
from app.modules.users.models import RoleName, User


def test_tenant_context_requires_an_active_tenant() -> None:
    tenant = Tenant(slug="acme", name="Acme", status=TenantStatus.SUSPENDED.value)
    tenant.id = uuid4()

    with pytest.raises(ValueError, match="active"):
        require_tenant_context(tenant)


def test_with_tenant_applies_the_tenant_predicate() -> None:
    tenant_id = uuid4()
    statement = with_tenant(select(User), tenant_id)

    compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert tenant_id.hex in compiled
    assert "tenant_id" in compiled


def test_tenant_defaults_are_safe() -> None:
    tenant = Tenant(slug="default", name="Default Tenant")

    assert tenant.status == TenantStatus.ACTIVE.value
    assert tenant.brand_name == "Default Tenant"
    assert tenant.currency == "INR"
    assert tenant.timezone == "UTC"
