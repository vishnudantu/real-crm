"""Cross-module require_permission rollout: built-in equivalence + custom grants.

Every converted staff router is exercised three ways:
- a built-in ADMIN/SALES_EXECUTIVE caller keeps today's access (regression
  guard against accidental gating changes);
- a custom role holding the mapped key can act;
- a custom role lacking the key is rejected with 403 (fail closed).

Custom-role users keep their built-in base role for row-level scoping, so
these tests assign the custom role to a SALES_EXECUTIVE base account.
"""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.projects.models import Project, ProjectStatus
from app.modules.users.models import RoleName, User

# Endpoint + payload per converted module for the allow/deny probe.
# Each tuple is (permission_key, method, path, json_payload_or_None).
PROBES: list[tuple[str, str, str, dict | None]] = [
    ("projects.write", "post", "/api/v1/projects", {"name": "Perm Probe", "slug": "perm-probe"}),
    ("leads.read", "get", "/api/v1/leads", None),
    ("leads.manage", "get", "/api/v1/leads/opted-out", None),
    ("customers.read", "get", "/api/v1/customers", None),
    ("customers.write", "post", "/api/v1/customers/contacts", {"display_name": "Perm Contact"}),
    ("brokers.read", "get", "/api/v1/brokers", None),
    ("postsales.read", "get", "/api/v1/sales-bookings/receipts/{uuid}", None),
    ("documents.read", "get", "/api/v1/documents", None),
    ("approvals.request", "get", "/api/v1/approvals/requests", None),
    ("messaging.configure", "get", "/api/v1/messaging/templates", None),
    ("teamchat.use", "get", "/api/v1/teamchat/channels", None),
    ("service_desk.use", "get", "/api/v1/service-desk/tickets", None),
    ("construction.read", "get", "/api/v1/construction/projects/{uuid}/milestones", None),
    ("reconciliation.read", "get", "/api/v1/reconciliation/transactions", None),
    ("voice_intel.read", "get", "/api/v1/voice-intel/transcriptions", None),
    ("tenant_ai.manage", "get", "/api/v1/tenant-ai/provider", None),
    ("integrations.manage", "get", "/api/v1/integrations/connections", None),
]


def _make_custom_role(
    client: TestClient,
    admin_headers: dict[str, str],
    *,
    permissions: list[str],
    name: str | None = None,
) -> dict:
    response = client.post(
        "/api/v1/roles/custom",
        headers=admin_headers,
        json={
            "name": name or f"Probe {uuid4().hex[:8]}",
            "description": "Cross-module permission probe.",
            "permissions": permissions,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _assign(
    client: TestClient,
    admin_headers: dict[str, str],
    user: User,
    role_id: str,
) -> None:
    response = client.patch(
        f"/api/v1/users/{user.id}",
        headers=admin_headers,
        json={"custom_role_id": role_id},
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("key,method,path,payload", PROBES)
def test_custom_role_grant_allows_and_absence_denies(
    client: TestClient,
    user_factory: Callable[..., User],
    auth_headers: Callable[..., dict[str, str]],
    key: str,
    method: str,
    path: str,
    payload: dict | None,
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    admin_headers = auth_headers(admin.email)
    real_path = path.replace("{uuid}", str(uuid4()))

    # Built-in ADMIN always passes (regression: built-in behavior unchanged).
    admin_response = client.request(method, real_path, headers=admin_headers, json=payload)
    assert admin_response.status_code != 403, (key, "admin", admin_response.text)

    # Custom role WITH the key can act.
    staff_with = user_factory(role=RoleName.SALES_EXECUTIVE)
    granted = _make_custom_role(client, admin_headers, permissions=[key])
    _assign(client, admin_headers, staff_with, granted["id"])
    with_headers = auth_headers(staff_with.email)
    with_response = client.request(method, real_path, headers=with_headers, json=payload)
    assert with_response.status_code != 403, (key, "granted", with_response.text)

    # Custom role WITHOUT the key gets 403.
    staff_without = user_factory(role=RoleName.SALES_EXECUTIVE)
    empty = _make_custom_role(client, admin_headers, permissions=["inventory.read"])
    _assign(client, admin_headers, staff_without, empty["id"])
    without_headers = auth_headers(staff_without.email)
    without_response = client.request(method, real_path, headers=without_headers, json=payload)
    assert without_response.status_code == 403, (key, "without", without_response.text)


def test_sales_base_builtin_behavior_unchanged(
    client: TestClient,
    user_factory: Callable[..., User],
    auth_headers: Callable[..., dict[str, str]],
) -> None:
    """A plain SALES_EXECUTIVE keeps access to every staff read surface."""

    sales = user_factory(role=RoleName.SALES_EXECUTIVE)
    headers = auth_headers(sales.email)
    for key, method, path, payload in PROBES:
        # Skip admin-only write surfaces: sales never had those.
        definition = None
        from app.modules.users.permissions import PERMISSION_REGISTRY

        definition = PERMISSION_REGISTRY[key]
        if definition.legacy_roles == frozenset({RoleName.ADMIN.value}):
            continue
        real_path = path.replace("{uuid}", str(uuid4()))
        response = client.request(method, real_path, headers=headers, json=payload)
        assert response.status_code != 403, (key, response.text)


# ---------------------------------------------------------------------------
# Base-role semantics (decision 4): assigning a custom role never demotes the
# built-in base role. Row-level service scoping still keys on that base role.
# ---------------------------------------------------------------------------


def _project_for(client, admin_headers, tenant_admin_id):
    from app.modules.projects.models import ProjectStatus
    from tests.project_support import create_project

    return create_project(client, admin_headers, status=ProjectStatus.ACTIVE.value)


def test_admin_with_custom_role_keeps_tenant_wide_lead_visibility(
    client: TestClient,
    user_factory: Callable[..., User],
    auth_headers: Callable[..., dict[str, str]],
) -> None:
    """An ADMIN given a custom role still sees all tenant leads, not just
    leads assigned to them (no silent demotion to SALES_EXECUTIVE scoping)."""
    from tests.lead_support import create_lead

    admin = user_factory(role=RoleName.ADMIN)
    admin_headers = auth_headers(admin.email)
    target_admin = user_factory(role=RoleName.ADMIN)
    project = _project_for(client, admin_headers, admin.id)
    create_lead(client, project_id=project["id"], email=f"scope-{uuid4().hex[:6]}@example.com")

    # Grant the target admin a custom role that includes leads.read only.
    role = _make_custom_role(client, admin_headers, permissions=["leads.read"])
    _assign(client, admin_headers, target_admin, role["id"])
    headers = auth_headers(target_admin.email)

    listing = client.get("/api/v1/leads", headers=headers)
    assert listing.status_code == 200, listing.text
    body = listing.json()
    # Tenant-wide: the lead exists and is visible (total >= 1, not exec-scoped 0).
    assert body["total"] >= 1


def test_sales_with_custom_role_keeps_executive_lead_scoping(
    client: TestClient,
    user_factory: Callable[..., User],
    auth_headers: Callable[..., dict[str, str]],
) -> None:
    """A SALES_EXECUTIVE given a custom role keeps exec scoping: they do NOT
    gain tenant-wide lead visibility just because they hold leads.read."""
    from tests.lead_support import create_lead

    admin = user_factory(role=RoleName.ADMIN)
    admin_headers = auth_headers(admin.email)
    sales = user_factory(role=RoleName.SALES_EXECUTIVE)
    project = _project_for(client, admin_headers, admin.id)
    create_lead(client, project_id=project["id"], email=f"scope-{uuid4().hex[:6]}@example.com")

    role = _make_custom_role(client, admin_headers, permissions=["leads.read"])
    _assign(client, admin_headers, sales, role["id"])
    headers = auth_headers(sales.email)

    listing = client.get("/api/v1/leads", headers=headers)
    assert listing.status_code == 200, listing.text
    body = listing.json()
    # Exec-scoped: the unassigned lead is not visible to this executive.
    assert body["total"] == 0


def test_admin_with_custom_role_is_not_demoted(
    client: TestClient,
    user_factory: Callable[..., User],
    auth_headers: Callable[..., dict[str, str]],
) -> None:
    """Assigning a custom role to an ADMIN preserves the ADMIN base role."""
    admin = user_factory(role=RoleName.ADMIN)
    admin_headers = auth_headers(admin.email)
    target_admin = user_factory(role=RoleName.ADMIN)
    role = _make_custom_role(client, admin_headers, permissions=["leads.read"])
    response = _assign_response(client, admin_headers, target_admin, role["id"])
    assert response.json()["role"]["name"] == RoleName.ADMIN.value


def _assign_response(client, admin_headers, user, role_id):
    response = client.patch(
        f"/api/v1/users/{user.id}",
        headers=admin_headers,
        json={"custom_role_id": role_id},
    )
    assert response.status_code == 200, response.text
    return response
