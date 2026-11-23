"""MANAGER inventory access without tenant administration privileges."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.modules.inventory.models import HoldState, UnitStatus
from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.projects.models import Project, ProjectStatus
from app.modules.users.models import RoleName, User


def _project_and_lead(
    session: Session, manager: User
) -> tuple[Project, Lead]:
    project = Project(
        tenant_id=manager.tenant_id,
        name="Manager Towers",
        slug=f"manager-{uuid4().hex[:8]}",
        location="Pune",
        status=ProjectStatus.ACTIVE.value,
        created_by=manager.id,
    )
    session.add(project)
    session.flush()
    lead = Lead(
        tenant_id=manager.tenant_id,
        full_name="Hold Buyer",
        email=f"hold-{uuid4().hex[:8]}@example.com",
        phone=f"91{uuid4().int % 10**10:010d}",
        project_id=project.id,
        source=LeadSource.WEBSITE.value,
        status=LeadStatus.CONVERTED.value,
        consent_to_contact=True,
    )
    session.add(lead)
    session.commit()
    return project, lead


def test_manager_can_manage_draft_units_and_place_holds(
    client,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> None:
    manager = user_factory(role=RoleName.MANAGER)
    headers = auth_headers(manager.email)
    with test_session_factory() as session:
        project, lead = _project_and_lead(session, session.get(User, manager.id))
        project_id, lead_id = project.id, lead.id

    created = client.post(
        "/api/v1/inventory/units",
        json={
            "project_id": str(project_id),
            "internal_code": "MGR-1",
            "configuration": "2 BHK",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    unit_id = created.json()["id"]
    assert created.json()["status"] == UnitStatus.DRAFT.value

    updated = client.patch(
        f"/api/v1/inventory/units/{unit_id}",
        json={"configuration": "3 BHK", "carpet_area_sqft": 1450},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["configuration"] == "3 BHK"

    for target in (UnitStatus.APPROVED, UnitStatus.AVAILABLE):
        transitioned = client.patch(
            f"/api/v1/inventory/units/{unit_id}/status",
            json={"to_status": target.value, "reason": "Manager publishing unit."},
            headers=headers,
        )
        assert transitioned.status_code == 200, transitioned.text
        assert transitioned.json()["status"] == target.value

    hold = client.post(
        "/api/v1/inventory/holds",
        json={"unit_id": unit_id, "lead_id": str(lead_id), "reason": "Buyer visit."},
        headers=headers,
    )
    assert hold.status_code == 201, hold.text
    assert hold.json()["state"] == HoldState.ACTIVE.value
    assert hold.json()["owner_user_id"] == str(manager.id)

    draft = client.post(
        "/api/v1/inventory/units",
        json={"project_id": str(project_id), "internal_code": "MGR-DRAFT"},
        headers=headers,
    )
    assert draft.status_code == 201, draft.text
    deleted = client.delete(
        f"/api/v1/inventory/units/{draft.json()['id']}", headers=headers
    )
    assert deleted.status_code == 204, deleted.text


def test_manager_cannot_manage_tenant_settings_or_user_roles(
    client, user_factory, auth_headers
) -> None:
    manager = user_factory(role=RoleName.MANAGER)
    other_user = user_factory(role=RoleName.SALES_EXECUTIVE)
    headers = auth_headers(manager.email)

    settings = client.put(
        "/api/v1/tenancy/settings",
        json={"brand_name": "Unauthorized change"},
        headers=headers,
    )
    assert settings.status_code == 403

    role_change = client.patch(
        f"/api/v1/users/{other_user.id}",
        json={"role": RoleName.ADMIN.value},
        headers=headers,
    )
    assert role_change.status_code == 403


def test_sales_executive_still_cannot_delete_a_unit(
    client,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    with test_session_factory() as session:
        project, _lead = _project_and_lead(session, session.get(User, admin.id))
        project_id = project.id
    created = client.post(
        "/api/v1/inventory/units",
        json={"project_id": str(project_id), "internal_code": "SALES-DELETE"},
        headers=auth_headers(admin.email),
    )
    assert created.status_code == 201, created.text

    sales = user_factory(role=RoleName.SALES_EXECUTIVE)
    deleted = client.delete(
        f"/api/v1/inventory/units/{created.json()['id']}",
        headers=auth_headers(sales.email),
    )
    assert deleted.status_code == 403


def test_buyer_cannot_manage_inventory(
    client,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    with test_session_factory() as session:
        project, _lead = _project_and_lead(session, session.get(User, admin.id))
        project_id = project.id
    created = client.post(
        "/api/v1/inventory/units",
        json={"project_id": str(project_id), "internal_code": "BUYER-READONLY"},
        headers=auth_headers(admin.email),
    )
    assert created.status_code == 201, created.text
    unit_id = created.json()["id"]
    buyer_headers = auth_headers(user_factory(role=RoleName.BUYER).email)

    listed = client.get("/api/v1/inventory/units", headers=buyer_headers)
    assert listed.status_code == 200
    responses = (
        client.post(
            "/api/v1/inventory/units",
            json={"project_id": str(project_id), "internal_code": "BUYER-CREATE"},
            headers=buyer_headers,
        ),
        client.patch(
            f"/api/v1/inventory/units/{unit_id}",
            json={"configuration": "Unauthorized"},
            headers=buyer_headers,
        ),
        client.delete(
            f"/api/v1/inventory/units/{unit_id}", headers=buyer_headers
        ),
        client.post(
            "/api/v1/inventory/holds",
            json={"unit_id": unit_id},
            headers=buyer_headers,
        ),
    )
    assert [response.status_code for response in responses] == [403, 403, 403, 403]
