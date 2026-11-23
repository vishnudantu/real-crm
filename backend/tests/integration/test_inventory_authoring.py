"""Project-type-aware inventory authoring: per-type unit validation on writes.

Rules encoded in app.modules.inventory.authoring.validate_unit_for_project_type:
- APARTMENT: tower + floor required; plot_number forbidden.
- VILLA / PLOT: plot_number required; tower forbidden; floor must be empty or a
  ground-block code like "G" or "B1".
- COMMERCIAL: tower + floor required; plot-style/suite identification stays
  allowed (suite codes may reuse internal_code, no extra restriction).
- MIXED or a project without a type: no per-type restrictions, so every
  existing row and legacy project keeps working (validation is write-only).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.security import hash_password
from app.modules.inventory import service
from app.modules.inventory.authoring import validate_unit_for_project_type
from app.modules.inventory.models import PropertyUnit, UnitStatus
from app.modules.inventory.schemas import UnitCreateRequest, UnitUpdateRequest
from app.modules.projects.models import Project, ProjectStatus, ProjectType
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD


def _fixture(
    session: Session, *, project_type: ProjectType | None = None
) -> tuple[Tenant, User, Project]:
    tenant = Tenant(slug=f"auth-{uuid4().hex[:8]}", name="Authoring Co")
    session.add(tenant)
    session.flush()
    role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one_or_none()
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    admin = User(
        tenant_id=tenant.id, full_name="Admin",
        email=f"a.{tenant.id.hex[:8]}@auth.example",
        password_hash=hash_password(TEST_PASSWORD), role_id=role.id, is_active=True,
    )
    session.add(admin)
    session.flush()
    project = Project(
        tenant_id=tenant.id, name="Typeful", slug=f"typeful-{uuid4().hex[:8]}",
        location="Pune", status=ProjectStatus.ACTIVE.value, created_by=admin.id,
        project_type=project_type.value if project_type is not None else None,
    )
    session.add(project)
    session.commit()
    return tenant, admin, project


def _unit_payload(project: Project, **overrides: object) -> UnitCreateRequest:
    fields: dict[str, object] = {
        "project_id": project.id,
        "internal_code": f"U-{uuid4().hex[:6]}",
        "configuration": "2 BHK",
        "carpet_area_sqft": 1000,
    }
    fields.update(overrides)
    return UnitCreateRequest(**fields)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Pure helper: validate_unit_for_project_type
# ---------------------------------------------------------------------------


def test_apartment_requires_tower_and_floor_and_forbids_plot() -> None:
    errors = validate_unit_for_project_type(
        "APARTMENT", {"tower": None, "floor": None, "plot_number": None}
    )
    assert len(errors) == 2
    assert any("Tower" in error for error in errors)
    assert any("Floor" in error for error in errors)

    assert validate_unit_for_project_type(
        "APARTMENT", {"tower": "A", "floor": "3", "plot_number": None}
    ) == []

    with_plot = validate_unit_for_project_type(
        "APARTMENT", {"tower": "A", "floor": "3", "plot_number": "P-9"}
    )
    assert len(with_plot) == 1
    assert "Plot number" in with_plot[0]


def test_villa_and_plot_require_plot_and_forbid_tower() -> None:
    for project_type in ("VILLA", "PLOT"):
        missing_plot = validate_unit_for_project_type(
            project_type, {"tower": None, "floor": None, "plot_number": None}
        )
        assert len(missing_plot) == 1, project_type
        assert "Plot number is required" in missing_plot[0]

        with_tower = validate_unit_for_project_type(
            project_type, {"tower": "A", "floor": None, "plot_number": "V-1"}
        )
        assert len(with_tower) == 1, project_type
        assert "Tower must be empty" in with_tower[0]

        assert validate_unit_for_project_type(
            project_type, {"tower": None, "floor": None, "plot_number": "V-1"}
        ) == []
        # Ground/basement block codes are the only floor values allowed.
        assert validate_unit_for_project_type(
            project_type, {"tower": None, "floor": "G", "plot_number": "V-1"}
        ) == []
        assert validate_unit_for_project_type(
            project_type, {"tower": None, "floor": "B1", "plot_number": "V-1"}
        ) == []
        storey_floor = validate_unit_for_project_type(
            project_type, {"tower": None, "floor": "12", "plot_number": "V-1"}
        )
        assert len(storey_floor) == 1, project_type
        assert "Floor" in storey_floor[0]


def test_commercial_requires_tower_and_floor_and_allows_suite_style_codes() -> None:
    missing = validate_unit_for_project_type(
        "COMMERCIAL", {"tower": None, "floor": None, "plot_number": None}
    )
    assert len(missing) == 2
    assert any("Tower" in error for error in missing)
    assert any("Floor" in error for error in missing)

    # A commercial suite may identify itself through the internal code and may
    # still carry a plot-style reference; only tower + floor are imposed.
    assert validate_unit_for_project_type(
        "COMMERCIAL", {"tower": "Zen", "floor": "4", "plot_number": "SHOP-7"}
    ) == []


def test_mixed_and_untyped_projects_impose_no_restrictions() -> None:
    unrestricted_fields = {"tower": None, "floor": None, "plot_number": "P-1"}
    assert validate_unit_for_project_type("MIXED", unrestricted_fields) == []
    assert validate_unit_for_project_type(None, unrestricted_fields) == []
    assert validate_unit_for_project_type(None, {"tower": "A", "floor": "2", "plot_number": None}) == []


# ---------------------------------------------------------------------------
# Wiring: create / bulk / update paths
# ---------------------------------------------------------------------------


def test_create_unit_rejects_apartment_row_without_tower(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, project = _fixture(session, project_type=ProjectType.APARTMENT)
        with pytest.raises(HTTPException) as exc:
            service.create_unit(
                session, actor=admin,
                payload=_unit_payload(project, floor="3", tower=None),
            )
        assert exc.value.status_code == 400
        assert "Tower" in str(exc.value.detail)

        created = service.create_unit(
            session, actor=admin,
            payload=_unit_payload(project, tower="A", floor="3"),
        )
        assert created.tower == "A"


def test_create_unit_rejects_villa_row_with_tower(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, project = _fixture(session, project_type=ProjectType.VILLA)
        with pytest.raises(HTTPException) as exc:
            service.create_unit(
                session, actor=admin,
                payload=_unit_payload(project, tower="A", plot_number="V-1"),
            )
        assert exc.value.status_code == 400
        assert "Tower must be empty" in str(exc.value.detail)


def test_bulk_create_reports_invalid_row_without_losing_siblings(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, project = _fixture(session, project_type=ProjectType.PLOT)
        valid_row = _unit_payload(project, internal_code="PLOT-1", plot_number="P-1")
        invalid_row = _unit_payload(project, internal_code="PLOT-2", plot_number=None)
        results = service.bulk_create_units(session, actor=admin, rows=[valid_row, invalid_row])
        assert results[0].ok is True
        assert results[1].ok is False
        assert "Plot number is required" in (results[1].reason or "")


def test_update_unit_cannot_violate_project_type(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, project = _fixture(session, project_type=ProjectType.VILLA)
        unit = service.create_unit(
            session, actor=admin,
            payload=_unit_payload(project, plot_number="V-1"),
        )
        with pytest.raises(HTTPException) as exc:
            service.update_unit(
                session, actor=admin, unit_id=unit.id,
                payload=UnitUpdateRequest(tower="A"),
            )
        assert exc.value.status_code == 400
        session.refresh(unit)
        assert unit.tower is None  # nothing was written

        # A compliant edit succeeds: ground block floors are allowed on villas.
        updated = service.update_unit(
            session, actor=admin, unit_id=unit.id,
            payload=UnitUpdateRequest(floor="G"),
        )
        assert updated.floor == "G"


def test_update_unit_cannot_clear_required_apartment_floor(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, project = _fixture(session, project_type=ProjectType.APARTMENT)
        unit = service.create_unit(
            session, actor=admin,
            payload=_unit_payload(project, tower="A", floor="3"),
        )
        with pytest.raises(HTTPException) as exc:
            service.update_unit(
                session, actor=admin, unit_id=unit.id,
                payload=UnitUpdateRequest(floor=None),
            )
        assert exc.value.status_code == 400
        session.refresh(unit)
        assert unit.floor == "3"


def test_mixed_project_accepts_tower_and_plot_units(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, project = _fixture(session, project_type=ProjectType.MIXED)
        tower_unit = service.create_unit(
            session, actor=admin, payload=_unit_payload(project, tower="A", floor="2")
        )
        plot_unit = service.create_unit(
            session, actor=admin, payload=_unit_payload(project, plot_number="P-8")
        )
        assert isinstance(tower_unit, PropertyUnit)
        assert isinstance(plot_unit, PropertyUnit)


def test_untyped_project_keeps_legacy_write_behavior(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        _tenant, admin, project = _fixture(session, project_type=None)
        unit = service.create_unit(
            session, actor=admin,
            payload=_unit_payload(project, tower="A", floor="12", plot_number=None),
        )
        assert unit.status == UnitStatus.DRAFT.value


def test_project_type_round_trip_over_api(
    client, override_db, seeded_roles, test_session_factory, user_factory, auth_headers,
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    headers = auth_headers(admin.email)
    created = client.post(
        "/api/v1/projects",
        json={"name": f"PT {uuid4().hex[:6]}", "location": "Pune", "project_type": "VILLA"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["project_type"] == "VILLA"

    project_id = created.json()["id"]
    updated = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"project_type": "COMMERCIAL"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["project_type"] == "COMMERCIAL"

    invalid = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"project_type": "IGLOO"},
        headers=headers,
    )
    assert invalid.status_code == 422
