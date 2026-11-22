"""Inventory unit field update and guarded delete (PF-010 extension)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.security import hash_password
from app.modules.inventory import service
from app.modules.inventory.models import PropertyUnit, UnitStatus
from app.modules.inventory.schemas import UnitCreateRequest, UnitUpdateRequest
from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD


def _fixture(session: Session) -> tuple[Tenant, User, Project, Lead]:
    tenant = Tenant(slug=f"invu-{uuid4().hex[:8]}", name="Inv Upd Co")
    session.add(tenant)
    session.flush()
    role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one_or_none()
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    admin = User(
        tenant_id=tenant.id, full_name="Admin", email=f"a.{tenant.id.hex[:8]}@invu.example",
        password_hash=hash_password(TEST_PASSWORD), role_id=role.id, is_active=True,
    )
    session.add(admin)
    session.flush()
    session.refresh(admin)
    project = Project(
        tenant_id=tenant.id, name="Towers", slug=f"towers-{tenant.id.hex[:8]}", location="Pune",
        status=ProjectStatus.ACTIVE.value, created_by=admin.id,
    )
    session.add(project)
    session.flush()
    lead = Lead(
        tenant_id=tenant.id, full_name="Buyer", email=f"b.{tenant.id.hex[:8]}@invu.example",
        phone="+919800000011", project_id=project.id, source=LeadSource.WEBSITE.value,
        status=LeadStatus.CONVERTED.value, consent_to_contact=True,
    )
    session.add(lead)
    session.commit()
    return tenant, admin, project, lead


def _unit(session: Session, admin: User, project: Project, *, status=UnitStatus.DRAFT) -> PropertyUnit:
    return service.create_unit(
        session, actor=admin,
        payload=UnitCreateRequest(
            project_id=project.id, internal_code=f"U-{uuid4().hex[:6]}",
            configuration="2 BHK", carpet_area_sqft=1000, status=status,
        ),
    )


def test_update_unit_edits_mutable_fields(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _t, admin, project, _lead = _fixture(session)
        unit = _unit(session, admin, project)
        updated = service.update_unit(
            session, actor=admin, unit_id=unit.id,
            payload=UnitUpdateRequest(
                configuration="3 BHK", carpet_area_sqft=1450, tower="B", floor="12",
                facing="East", views="Lake", saleable=True,
            ),
        )
        assert updated.configuration == "3 BHK"
        assert updated.carpet_area_sqft == 1450
        assert updated.tower == "B"
        assert updated.floor == "12"
        assert updated.facing == "East"
        assert updated.views == "Lake"


def test_update_unit_code_is_immutable(
    test_session_factory: sessionmaker[Session],
) -> None:
    # internal_code is not on the update schema at all, so it cannot be changed.
    from app.modules.inventory.schemas import UnitUpdateRequest as UUR
    assert "internal_code" not in UUR.model_fields


def test_delete_draft_unit_succeeds(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _t, admin, project, _lead = _fixture(session)
        unit = _unit(session, admin, project, status=UnitStatus.DRAFT)
        service.delete_unit(session, actor=admin, unit_id=unit.id)
        assert session.get(PropertyUnit, unit.id) is None


def test_delete_non_draft_unit_rejected(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _t, admin, project, _lead = _fixture(session)
        unit = _unit(session, admin, project, status=UnitStatus.AVAILABLE)
        with pytest.raises(HTTPException) as exc:
            service.delete_unit(session, actor=admin, unit_id=unit.id)
        assert exc.value.status_code == 400


def test_delete_unit_with_hold_rejected(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _t, admin, project, lead = _fixture(session)
        unit = _unit(session, admin, project, status=UnitStatus.AVAILABLE)
        service.acquire_hold(session, actor=admin, unit_id=unit.id, lead_id=lead.id)
        # Force status back to DRAFT is not allowed; delete is blocked by state anyway.
        with pytest.raises(HTTPException) as exc:
            service.delete_unit(session, actor=admin, unit_id=unit.id)
        assert exc.value.status_code == 400


def test_update_unit_api_and_delete_api(
    client, override_db, seeded_roles, test_session_factory, user_factory, auth_headers,
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    headers = auth_headers(admin.email)
    with test_session_factory() as session:
        admin = session.get(User, admin.id)
        tenant = session.get(Tenant, admin.tenant_id)
        project = Project(
            tenant_id=tenant.id, name="API Towers", slug=f"apit-{tenant.id.hex[:6]}", location="Pune",
            status=ProjectStatus.ACTIVE.value, created_by=admin.id,
        )
        session.add(project)
        session.commit()
        unit = _unit(session, admin, project)
        unit_id = unit.id

    r = client.patch(
        f"/api/v1/inventory/units/{unit_id}",
        json={"configuration": "4 BHK", "carpet_area_sqft": 2000, "tower": "C"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["configuration"] == "4 BHK"
    assert r.json()["tower"] == "C"

    d = client.delete(f"/api/v1/inventory/units/{unit_id}", headers=headers)
    assert d.status_code == 204
    gone = client.get(f"/api/v1/inventory/units/{unit_id}", headers=headers)
    assert gone.status_code == 404
