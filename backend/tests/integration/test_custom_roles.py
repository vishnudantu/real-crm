"""Custom role designer, tenant isolation, and permission-gated inventory."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.dependencies import require_permission, require_roles
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from app.modules.users.permissions import (
    GRANTABLE_PERMISSIONS,
    PERMISSION_REGISTRY,
    PROTECTED_PERMISSIONS,
    validate_permissions,
)
from tests.support import TEST_PASSWORD


def _create_role(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Inventory Coordinator",
    permissions: list[str] | None = None,
):
    return client.post(
        "/api/v1/roles/custom",
        headers=headers,
        json={
            "name": name,
            "description": "Tenant-scoped inventory operations.",
            "permissions": permissions or ["inventory.read", "inventory.write"],
        },
    )


def _other_tenant_admin(
    test_session_factory: sessionmaker[Session],
    user_factory: Callable[..., User],
) -> User:
    with test_session_factory() as session:
        tenant = Tenant(slug=f"role-other-{uuid4().hex[:8]}", name="Other Role Co")
        session.add(tenant)
        session.commit()
        session.refresh(tenant)
        return user_factory(
            role=RoleName.ADMIN,
            tenant=tenant,
            email=f"other-role-{uuid4().hex[:8]}@example.com",
        )


def test_permission_registry_shape_and_validation(
    client: TestClient,
    user_factory: Callable[..., User],
    auth_headers: Callable[..., dict[str, str]],
) -> None:
    assert len(PERMISSION_REGISTRY) == 30
    assert len(GRANTABLE_PERMISSIONS) == 26
    assert PROTECTED_PERMISSIONS == {
        "settings.manage", "users.manage", "roles.manage", "operator.access"
    }
    assert validate_permissions([" inventory.write ", "inventory.write"]) == [
        "inventory.write"
    ]
    with pytest.raises(ValueError, match="Unknown permission"):
        validate_permissions(["inventory.unknown"])
    from app.modules.users.models import CustomRole

    with pytest.raises(ValueError, match="Unknown permission"):
        CustomRole(permissions=["future.unrecognized"])
    with pytest.raises(ValueError, match="cannot be granted"):
        validate_permissions(["settings.manage"])

    admin = user_factory(role=RoleName.ADMIN)
    headers = auth_headers(admin.email)
    response = client.get("/api/v1/roles/permissions", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 30
    assert {item["key"] for item in body["items"]} == set(PERMISSION_REGISTRY)
    assert all(
        {"key", "area", "description", "grantable", "enabled"} == set(item)
        for item in body["items"]
    )
    enabled = {item["key"] for item in body["items"] if item["enabled"]}
    assert enabled == {"inventory.read", "inventory.write", "inventory.holds"}
    settings = next(item for item in body["items"] if item["key"] == "settings.manage")
    assert settings["grantable"] is False
    with pytest.raises(ValueError, match="Unknown grantable"):
        require_permission("settings.manage")
    with pytest.raises(ValueError, match="Unknown grantable"):
        require_permission("inventory.unknown")


def test_custom_role_crud_and_cross_tenant_404(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
    user_factory: Callable[..., User],
    auth_headers: Callable[..., dict[str, str]],
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    headers = auth_headers(admin.email)
    created = _create_role(client, headers)
    assert created.status_code == 201, created.text
    role = created.json()
    assert role["name"] == "Inventory Coordinator"
    assert role["tenant_id"] == str(admin.tenant_id)
    assert role["created_by"] == str(admin.id)
    assert role["is_builtin"] is False
    assert role["permissions"] == ["inventory.read", "inventory.write"]

    listed = client.get("/api/v1/roles/custom", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == role["id"]

    updated = client.patch(
        f"/api/v1/roles/custom/{role['id']}",
        headers=headers,
        json={"name": "Unit Controller", "permissions": ["inventory.write"]},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Unit Controller"
    assert updated.json()["permissions"] == ["inventory.write"]

    other_admin = _other_tenant_admin(test_session_factory, user_factory)
    other_headers = auth_headers(other_admin.email)
    cross_tenant_patch = client.patch(
        f"/api/v1/roles/custom/{role['id']}",
        headers=other_headers,
        json={"description": "Not visible across tenants"},
    )
    cross_tenant_delete = client.delete(
        f"/api/v1/roles/custom/{role['id']}", headers=other_headers
    )
    other_list = client.get("/api/v1/roles/custom", headers=other_headers)
    assert cross_tenant_patch.status_code == 404
    assert cross_tenant_delete.status_code == 404
    assert other_list.json()["total"] == 0

    duplicate = _create_role(client, headers, name="Unit Controller")
    assert duplicate.status_code == 409
    same_name_other_tenant = _create_role(client, other_headers, name="Unit Controller")
    assert same_name_other_tenant.status_code == 201
    cross_tenant_assignment = client.patch(
        f"/api/v1/users/{admin.id}",
        headers=other_headers,
        json={"custom_role_id": role["id"]},
    )
    assert cross_tenant_assignment.status_code == 404

    # Built-in roles are never interpreted as tenant custom-role ids.
    builtin_edit = client.patch(
        f"/api/v1/roles/custom/{admin.role_id}",
        headers=headers,
        json={"name": "Changed Administrator"},
    )
    assert builtin_edit.status_code == 404
    deleted = client.delete(f"/api/v1/roles/custom/{role['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get("/api/v1/roles/custom", headers=headers).json()["total"] == 0


def test_custom_role_validation_and_admin_only_design(
    client: TestClient,
    user_factory: Callable[..., User],
    auth_headers: Callable[..., dict[str, str]],
) -> None:
    sales = user_factory(role=RoleName.SALES_EXECUTIVE)
    sales_headers = auth_headers(sales.email)
    assert client.get("/api/v1/roles/custom", headers=sales_headers).status_code == 403
    assert client.get("/api/v1/roles/permissions", headers=sales_headers).status_code == 403
    assert _create_role(client, sales_headers).status_code == 403

    admin_headers = auth_headers(user_factory(role=RoleName.ADMIN).email)
    protected = _create_role(client, admin_headers, permissions=["settings.manage"])
    unknown = _create_role(client, admin_headers, permissions=["inventory.superuser"])
    immutable = client.post(
        "/api/v1/roles/custom",
        headers=admin_headers,
        json={"name": "Fake Builtin", "permissions": [], "is_builtin": True},
    )
    immutable_role = _create_role(client, admin_headers, name="Editable Custom Role").json()
    builtin_edit = client.patch(
        f"/api/v1/roles/custom/{immutable_role['id']}",
        headers=admin_headers,
        json={"is_builtin": True},
    )
    assert protected.status_code == 422
    assert unknown.status_code == 422
    assert immutable.status_code == 422
    assert builtin_edit.status_code == 422


def test_direct_custom_user_creation_and_invalid_role_do_not_leak_account(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
    user_factory: Callable[..., User],
    auth_headers: Callable[..., dict[str, str]],
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    headers = auth_headers(admin.email)
    role = _create_role(client, headers).json()
    payload = {
        "full_name": "Direct Custom Staff",
        "email": f"direct-{uuid4().hex[:8]}@example.com",
        "password": TEST_PASSWORD,
        "custom_role_id": role["id"],
    }
    created = client.post("/api/v1/users", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["custom_role"]["id"] == role["id"]
    assert client.get(
        "/api/v1/inventory/units", headers=auth_headers(payload["email"])
    ).status_code == 200

    invalid_payload = dict(payload, email=f"invalid-{uuid4().hex[:8]}@example.com", custom_role_id=str(uuid4()))
    rejected = client.post("/api/v1/users", headers=headers, json=invalid_payload)
    assert rejected.status_code == 400
    assert client.post(
        "/api/v1/auth/login",
        json={"email": invalid_payload["email"], "password": TEST_PASSWORD},
    ).status_code == 401
    with test_session_factory() as session:
        assert not any(
            user.email == invalid_payload["email"]
            for user in session.query(User).all()
        )


def test_role_in_use_cannot_be_deleted_and_user_can_authenticate(
    client: TestClient,
    user_factory: Callable[..., User],
    auth_headers: Callable[..., dict[str, str]],
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    headers = auth_headers(admin.email)
    role = _create_role(client, headers).json()
    staff = user_factory(role=RoleName.SALES_EXECUTIVE)

    assigned = client.patch(
        f"/api/v1/users/{staff.id}",
        headers=headers,
        json={"custom_role_id": role["id"]},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["custom_role"]["id"] == role["id"]
    assert assigned.json()["custom_role"]["is_builtin"] is False
    assert assigned.json()["custom_role"]["permissions"] == [
        "inventory.read", "inventory.write"
    ]

    staff_headers = auth_headers(staff.email)
    profile = client.get("/api/v1/auth/me", headers=staff_headers)
    assert profile.status_code == 200
    assert profile.json()["custom_role"]["name"] == role["name"]
    assert client.delete(
        f"/api/v1/roles/custom/{role['id']}", headers=headers
    ).status_code == 409

    reassigned = client.patch(
        f"/api/v1/users/{staff.id}",
        headers=headers,
        json={"role": "SALES_EXECUTIVE"},
    )
    assert reassigned.status_code == 200
    assert reassigned.json()["custom_role"] is None
    assert client.delete(
        f"/api/v1/roles/custom/{role['id']}", headers=headers
    ).status_code == 204


def test_custom_inventory_role_allow_deny_and_system_boundary(
    client: TestClient,
    test_session_factory: sessionmaker[Session],
    user_factory: Callable[..., User],
    auth_headers: Callable[..., dict[str, str]],
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    admin_headers = auth_headers(admin.email)
    role = _create_role(client, admin_headers).json()
    staff = user_factory(role=RoleName.SALES_EXECUTIVE)
    assigned = client.patch(
        f"/api/v1/users/{staff.id}",
        headers=admin_headers,
        json={"custom_role_id": role["id"]},
    )
    assert assigned.status_code == 200
    headers = auth_headers(staff.email)

    with test_session_factory() as session:
        project = Project(
            tenant_id=admin.tenant_id,
            name="Custom Role Towers",
            slug=f"custom-role-{uuid4().hex[:8]}",
            location="Pune",
            status=ProjectStatus.ACTIVE.value,
            created_by=admin.id,
        )
        session.add(project)
        session.commit()
        project_id = project.id

    created = client.post(
        "/api/v1/inventory/units",
        headers=headers,
        json={"project_id": str(project_id), "internal_code": "CUSTOM-1"},
    )
    assert created.status_code == 201, created.text
    unit_id = created.json()["id"]
    updated = client.patch(
        f"/api/v1/inventory/units/{unit_id}",
        headers=headers,
        json={"configuration": "3 BHK"},
    )
    assert updated.status_code == 200, updated.text
    assert client.get("/api/v1/inventory/units", headers=headers).status_code == 200

    for method, path, payload in (
        ("get", "/api/v1/settings", None),
        ("put", "/api/v1/tenancy/settings", {"brand_name": "Forbidden"}),
        ("get", "/api/v1/users", None),
        ("get", "/api/v1/roles/custom", None),
    ):
        response = client.request(method.upper(), path, headers=headers, json=payload)
        assert response.status_code == 403, (path, response.text)

    read_only = _create_role(
        client,
        admin_headers,
        name="Read Only Inventory",
        permissions=["inventory.read"],
    ).json()
    reader = user_factory(role=RoleName.SALES_EXECUTIVE)
    assert client.patch(
        f"/api/v1/users/{reader.id}",
        headers=admin_headers,
        json={"custom_role_id": read_only["id"]},
    ).status_code == 200
    reader_headers = auth_headers(reader.email)
    assert client.get("/api/v1/inventory/units", headers=reader_headers).status_code == 200
    assert client.post(
        "/api/v1/inventory/units",
        headers=reader_headers,
        json={"project_id": str(project_id), "internal_code": "CUSTOM-DENIED"},
    ).status_code == 403
    assert client.post(
        "/api/v1/inventory/holds",
        headers=headers,
        json={"unit_id": unit_id},
    ).status_code == 403

    # A custom role never inherits its underlying SALES_EXECUTIVE legacy gate.
    assert client.get("/api/v1/leads", headers=headers).status_code == 403


def test_cross_tenant_direct_assignment_cannot_authenticate(
    test_session_factory: sessionmaker[Session],
    client: TestClient,
    user_factory: Callable[..., User],
    auth_headers: Callable[..., dict[str, str]],
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    staff = user_factory(role=RoleName.SALES_EXECUTIVE)
    other_admin = _other_tenant_admin(test_session_factory, user_factory)
    with test_session_factory() as session:
        foreign_role = _create_role_for_test(
            session, admin=session.get(User, other_admin.id)
        )
        target = session.get(User, staff.id)
        target.custom_role_id = foreign_role.id
        session.commit()
    headers = auth_headers(staff.email)
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401


def test_unrecognized_stored_permission_fails_closed(
    isolated_app,
    test_session_factory: sessionmaker[Session],
    user_factory: Callable[..., User],
) -> None:
    from fastapi import Depends

    from app.db.session import get_db
    from app.modules.auth.dependencies import get_current_user

    @isolated_app.get("/test-permission", dependencies=[Depends(require_permission("inventory.write"))])
    def protected(actor=Depends(get_current_user)):
        return {"id": str(actor.id)}

    @isolated_app.get("/test-legacy", dependencies=[Depends(require_roles(RoleName.SALES_EXECUTIVE))])
    def legacy(actor=Depends(get_current_user)):
        return {"id": str(actor.id)}

    def _test_db():
        with test_session_factory() as session:
            yield session

    isolated_app.dependency_overrides[get_db] = _test_db
    admin = user_factory(role=RoleName.ADMIN)
    staff = user_factory(role=RoleName.SALES_EXECUTIVE)
    with test_session_factory() as session:
        role = _create_role_for_test(session, admin=admin)
        target = session.get(User, staff.id)
        target.custom_role_id = role.id
        session.commit()
        from app.modules.auth.security import create_access_token
        from app.core.config import get_settings

        token = create_access_token(
            user_id=staff.id,
            role_name=role.name,
            tenant_id=staff.tenant_id,
            security_version=target.security_version,
            settings=get_settings(),
        )
    with TestClient(isolated_app) as test_client:
        headers = {"Authorization": f"Bearer {token}"}
        assert test_client.get("/test-permission", headers=headers).status_code == 200
        assert test_client.get("/test-legacy", headers=headers).status_code == 403
        with test_session_factory() as session:
            from sqlalchemy import text

            session.execute(
                text("UPDATE custom_roles SET permissions = :permissions WHERE id = :id"),
                {
                    "permissions": '["inventory.write", "future.unrecognized"]',
                    "id": role.id.hex,
                },
            )
            session.commit()
        assert test_client.get("/test-permission", headers=headers).status_code == 403


def _create_role_for_test(session: Session, *, admin: User):
    from app.modules.users.models import CustomRole

    role = CustomRole(
        tenant_id=admin.tenant_id,
        name=f"Direct role {uuid4().hex[:6]}",
        permissions=["inventory.write"],
        is_builtin=False,
        created_by=admin.id,
    )
    session.add(role)
    session.commit()
    return role
