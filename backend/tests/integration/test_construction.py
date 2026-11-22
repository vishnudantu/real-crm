"""Integration tests for construction milestones and certification."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.modules.construction.models import (
    ConstructionMilestone,
    MilestoneStatus,
    MilestoneUpdate,
)
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName


@pytest.fixture()
def env(
    client: TestClient,
    override_db: None,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> dict:
    admin = user_factory(role=RoleName.ADMIN)
    other_tenant = Tenant(slug=f"construction-{uuid4().hex[:8]}", name="Other Builder")
    with test_session_factory() as session:
        session.add(other_tenant)
        session.commit()
    outsider = user_factory(role=RoleName.ADMIN, tenant=other_tenant)
    sales = user_factory(role=RoleName.SALES_EXECUTIVE)
    with test_session_factory() as session:
        project = Project(
            tenant_id=admin.tenant_id,
            name="Construction Towers",
            slug=f"construction-{uuid4().hex[:8]}",
            location="Hyderabad",
            status=ProjectStatus.ACTIVE.value,
            created_by=admin.id,
        )
        foreign_project = Project(
            tenant_id=outsider.tenant_id,
            name="Foreign Towers",
            slug=f"foreign-{uuid4().hex[:8]}",
            location="Hyderabad",
            status=ProjectStatus.ACTIVE.value,
            created_by=outsider.id,
        )
        session.add_all([project, foreign_project])
        session.commit()
        return {
            "factory": test_session_factory,
            "tenant_id": admin.tenant_id,
            "admin_id": admin.id,
            "headers": auth_headers(admin.email),
            "foreign_headers": auth_headers(outsider.email),
            "sales_headers": auth_headers(sales.email),
            "project_id": project.id,
            "foreign_project_id": foreign_project.id,
        }


def _create_milestone(client: TestClient, env: dict, **overrides) -> dict:
    payload = {
        "project_id": str(env["project_id"]),
        "name": "Foundation",
        "sequence_no": 1,
        "planned_date": str(date.today() + timedelta(days=30)),
    }
    payload.update(overrides)
    response = client.post(
        "/api/v1/construction/milestones",
        json=payload,
        headers=env["headers"],
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_milestone_defaults_and_sales_can_read(client: TestClient, env: dict) -> None:
    milestone = _create_milestone(client, env)
    assert milestone["name"] == "Foundation"
    assert milestone["status"] == "NOT_STARTED"
    assert milestone["percent_complete"] == 0
    assert milestone["actual_date"] is None

    response = client.get(
        f"/api/v1/construction/projects/{env['project_id']}/milestones",
        headers=env["sales_headers"],
    )
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()] == [milestone["id"]]


def test_progress_updates_percent_and_transitions_to_completed(
    client: TestClient, env: dict
) -> None:
    milestone_id = _create_milestone(client, env)["id"]

    in_progress = client.post(
        f"/api/v1/construction/milestones/{milestone_id}/progress",
        json={"percent_complete": 40, "note": "Footings poured."},
        headers=env["headers"],
    )
    assert in_progress.status_code == 200, in_progress.text
    assert in_progress.json()["percent_complete"] == 40
    assert in_progress.json()["status"] == "IN_PROGRESS"

    completed = client.post(
        f"/api/v1/construction/milestones/{milestone_id}/progress",
        json={"percent_complete": 100, "note": "Foundation complete."},
        headers=env["headers"],
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "COMPLETED"
    assert completed.json()["actual_date"] is not None

    with env["factory"]() as session:
        updates = session.scalars(
            select(MilestoneUpdate).where(
                MilestoneUpdate.milestone_id == UUID(milestone_id)
            )
        ).all()
        assert [(row.percent_complete, row.note) for row in updates] == [
            (40, "Footings poured."),
            (100, "Foundation complete."),
        ]
        assert all(row.author_id == env["admin_id"] for row in updates)


def test_incomplete_past_planned_date_is_delayed(client: TestClient, env: dict) -> None:
    milestone_id = _create_milestone(
        client,
        env,
        planned_date=str(date.today() - timedelta(days=1)),
    )["id"]
    response = client.post(
        f"/api/v1/construction/milestones/{milestone_id}/progress",
        json={"percent_complete": 60, "note": "Behind schedule."},
        headers=env["headers"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "DELAYED"
    # Delayed-but-incomplete milestones have no completion date.
    assert response.json()["actual_date"] is None


def test_certification_requires_completion_and_records_actor(
    client: TestClient, env: dict
) -> None:
    milestone_id = _create_milestone(client, env)["id"]
    premature = client.post(
        f"/api/v1/construction/milestones/{milestone_id}/certify",
        json={"evidence_notes": "Not ready."},
        headers=env["headers"],
    )
    assert premature.status_code == 400

    client.post(
        f"/api/v1/construction/milestones/{milestone_id}/progress",
        json={"percent_complete": 100, "note": "Complete."},
        headers=env["headers"],
    )
    certified = client.post(
        f"/api/v1/construction/milestones/{milestone_id}/certify",
        json={"evidence_notes": "Engineer certificate verified."},
        headers=env["headers"],
    )
    assert certified.status_code == 200, certified.text
    body = certified.json()
    assert body["status"] == "CERTIFIED"
    assert body["certified_by_id"] == str(env["admin_id"])
    assert body["certified_at"] is not None
    assert body["evidence_notes"] == "Engineer certificate verified."


def test_progress_summary_aggregates_and_counts_delayed(
    client: TestClient, env: dict
) -> None:
    first_id = _create_milestone(client, env)["id"]
    second_id = _create_milestone(
        client,
        env,
        name="Podium",
        sequence_no=2,
        planned_date=str(date.today() - timedelta(days=2)),
    )["id"]
    _create_milestone(client, env, name="Tower slab", sequence_no=3)
    for milestone_id, percent in ((first_id, 100), (second_id, 50)):
        response = client.post(
            f"/api/v1/construction/milestones/{milestone_id}/progress",
            json={"percent_complete": percent, "note": "Site update."},
            headers=env["headers"],
        )
        assert response.status_code == 200, response.text

    response = client.get(
        f"/api/v1/construction/projects/{env['project_id']}/progress",
        headers=env["sales_headers"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    assert body["by_status"] == {
        "NOT_STARTED": 1,
        "COMPLETED": 1,
        "DELAYED": 1,
    }
    assert body["avg_percent"] == 50.0
    assert body["delayed_count"] == 1


def test_cross_tenant_resources_return_404(client: TestClient, env: dict) -> None:
    milestone = _create_milestone(client, env)
    responses = [
        client.get(
            f"/api/v1/construction/projects/{env['foreign_project_id']}/milestones",
            headers=env["headers"],
        ),
        client.get(
            f"/api/v1/construction/projects/{env['project_id']}/progress",
            headers=env["foreign_headers"],
        ),
        client.post(
            f"/api/v1/construction/milestones/{milestone['id']}/progress",
            json={"percent_complete": 25, "note": "Intrusion."},
            headers=env["foreign_headers"],
        ),
        client.post(
            f"/api/v1/construction/milestones/{milestone['id']}/certify",
            json={},
            headers=env["foreign_headers"],
        ),
    ]
    assert [response.status_code for response in responses] == [404, 404, 404, 404]


def test_sequence_is_unique_within_tenant_project(
    client: TestClient, env: dict
) -> None:
    _create_milestone(client, env)
    duplicate = client.post(
        "/api/v1/construction/milestones",
        json={
            "project_id": str(env["project_id"]),
            "name": "Duplicate",
            "sequence_no": 1,
            "planned_date": str(date.today()),
        },
        headers=env["headers"],
    )
    assert duplicate.status_code == 409, duplicate.text
    with env["factory"]() as session:
        count = len(
            session.scalars(
                select(ConstructionMilestone).where(
                    ConstructionMilestone.project_id == env["project_id"]
                )
            ).all()
        )
        assert count == 1

    # The database constraint also covers direct service/repository writers.
    with env["factory"]() as session:
        session.add(
            ConstructionMilestone(
                tenant_id=env["tenant_id"],
                project_id=env["project_id"],
                name="Direct duplicate",
                sequence_no=1,
                planned_date=date.today(),
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()
