"""Regression checks for the dedicated Hyderabad solar demo seed helper."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.inventory.models import PropertyUnit
from app.modules.projects.models import FactStatus, Project, ProjectFact
from app.modules.solar.models import TowerOrientation
from app.modules.solar.service import get_unit_sun_score
from app.modules.users.models import RoleName, User
from scripts.prepare_demo_environment import (
    SOLAR_DEMO_SLUG,
    reset_hyderabad_solar_demo,
    seed_hyderabad_solar_demo,
)


def test_hyderabad_solar_demo_is_idempotent_and_resets_cleanly(
    test_session_factory: sessionmaker[Session],
    user_factory: Callable[..., User],
) -> None:
    with test_session_factory() as session:
        admin = user_factory(role=RoleName.ADMIN)
        for _run in range(2):
            counts = seed_hyderabad_solar_demo(session, admin_user=admin)
            assert counts == {"towers": 4, "units": 6, "facts": 2}
            project = session.scalar(
                select(Project).where(Project.slug == SOLAR_DEMO_SLUG)
            )
            assert project is not None
            assert (project.latitude, project.longitude) == (17.38, 78.48)
            assert session.query(TowerOrientation).count() == 4
            assert session.query(PropertyUnit).count() == 6
            facts = session.scalars(
                select(ProjectFact).where(ProjectFact.project_id == project.id)
            ).all()
            assert len(facts) == 2
            assert all(fact.status == FactStatus.DRAFT.value for fact in facts)

        inherited_unit = session.scalar(
            select(PropertyUnit).where(PropertyUnit.internal_code == "D-604")
        )
        assert inherited_unit is not None
        assert inherited_unit.facing_deg is None
        score = get_unit_sun_score(
            session, tenant_id=admin.tenant_id, unit_id=inherited_unit.id
        )
        assert score.facing_label == "W"

        reset_hyderabad_solar_demo(session)
        assert session.query(Project).count() == 0
        assert session.query(TowerOrientation).count() == 0
        assert session.query(PropertyUnit).count() == 0
        assert session.query(ProjectFact).count() == 0
