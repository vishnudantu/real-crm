"""Tenant-scoped sales-floor aggregation and deterministic routing tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.modules.approvals.models import ApprovalRequest, ApprovalStatus
from app.modules.bookings.models import Booking, BookingStatus, VisitSlot
from app.modules.conversations.models import (
    Conversation,
    ConversationStatus,
    Message,
    MessageSenderType,
)
from app.modules.follow_ups.models import FollowUp, FollowUpStatus
from app.modules.leads.models import Lead, LeadAssignment, LeadSource, LeadStatus
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from tests.support import TEST_PASSWORD

NOW = datetime.now(UTC)
DAY_START = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
TOMORROW = DAY_START + timedelta(days=1)


def _project(tenant_id: UUID, creator_id: UUID, name: str) -> Project:
    return Project(
        tenant_id=tenant_id,
        name=name,
        slug=name.lower().replace(" ", "-"),
        location="Pune",
        created_by=creator_id,
        status=ProjectStatus.ACTIVE.value,
    )


def _lead(
    tenant_id: UUID,
    project_id: UUID,
    *,
    name: str,
    created_at: datetime,
    language: str = "en",
) -> Lead:
    return Lead(
        tenant_id=tenant_id,
        project_id=project_id,
        full_name=name,
        email=f"{name.lower().replace(' ', '.')}@example.com",
        phone="+919876543210",
        source=LeadSource.WEBSITE.value,
        status=LeadStatus.NEW.value,
        consent_to_contact=True,
        language=language,
        created_at=created_at,
        updated_at=created_at,
    )


def _assignment(
    tenant_id: UUID,
    lead: Lead,
    executive: User,
    assigner: User,
    *,
    unassigned_at: datetime | None = None,
) -> LeadAssignment:
    return LeadAssignment(
        tenant_id=tenant_id,
        lead_id=lead.id,
        executive_id=executive.id,
        assigned_by=assigner.id,
        assigned_at=lead.created_at,
        unassigned_at=unassigned_at,
    )


@pytest.fixture()
def sales_user(user_factory: Callable[..., User]) -> User:
    return user_factory(role=RoleName.SALES_EXECUTIVE, email="sales-floor-exec@example.com")


@pytest.fixture()
def manager_user(user_factory: Callable[..., User]) -> User:
    return user_factory(role=RoleName.MANAGER, email="sales-floor-manager@example.com")


@pytest.fixture()
def buyer_user(user_factory: Callable[..., User]) -> User:
    return user_factory(role=RoleName.BUYER, email="sales-floor-buyer@example.com")


def _api(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_my_day_prioritizes_explainable_items_and_excludes_other_executives(
    client: TestClient,
    override_db: None,
    test_session_factory: Callable[..., object],
    sales_user: User,
    manager_user: User,
    user_factory: Callable[..., User],
) -> None:
    other = user_factory(role=RoleName.SALES_EXECUTIVE, email="sales-floor-other@example.com")
    with test_session_factory() as session:
        project = _project(sales_user.tenant_id, manager_user.id, "Sales Floor Homes")
        session.add(project)
        session.flush()
        leads = [
            _lead(sales_user.tenant_id, project.id, name=f"Lead {index}", created_at=NOW - timedelta(hours=5 + index))
            for index in range(5)
        ]
        other_lead = _lead(
            sales_user.tenant_id, project.id, name="Other Lead", created_at=NOW - timedelta(hours=9)
        )
        session.add_all([*leads, other_lead])
        session.flush()
        for index, lead in enumerate(leads):
            lead.created_at = NOW - timedelta(hours=5 + index)
        session.add_all([_assignment(sales_user.tenant_id, lead, sales_user, manager_user) for lead in leads])
        session.add(_assignment(sales_user.tenant_id, other_lead, other, manager_user))
        session.add_all(
            [
                FollowUp(
                    tenant_id=sales_user.tenant_id,
                    lead_id=leads[0].id,
                    project_id=project.id,
                    executive_id=sales_user.id,
                    scheduled_at=DAY_START - timedelta(hours=1),
                    status=FollowUpStatus.PENDING.value,
                ),
                FollowUp(
                    tenant_id=sales_user.tenant_id,
                    lead_id=other_lead.id,
                    project_id=project.id,
                    executive_id=other.id,
                    scheduled_at=DAY_START - timedelta(days=3),
                    status=FollowUpStatus.PENDING.value,
                ),
            ]
        )
        slot = VisitSlot(
            tenant_id=sales_user.tenant_id,
            project_id=project.id,
            start_time=TOMORROW - timedelta(hours=8),
            end_time=TOMORROW - timedelta(hours=7),
        )
        session.add(slot)
        session.flush()
        session.add(
            Booking(
                tenant_id=sales_user.tenant_id,
                slot_id=slot.id,
                lead_id=leads[1].id,
                project_id=project.id,
                buyer_id=manager_user.id,
                executive_id=sales_user.id,
                status=BookingStatus.CONFIRMED.value,
            )
        )
        conversation = Conversation(
            tenant_id=sales_user.tenant_id,
            lead_id=leads[2].id,
            project_id=project.id,
            buyer_id=manager_user.id,
            status=ConversationStatus.ACTIVE.value,
        )
        session.add(conversation)
        session.flush()
        session.add(
            Message(
                tenant_id=sales_user.tenant_id,
                conversation_id=conversation.id,
                sender_type=MessageSenderType.BUYER.value,
                sender_id=manager_user.id,
                content="Could you share the floor plan?",
                created_at=NOW - timedelta(hours=2),
            )
        )
        session.add(
            ApprovalRequest(
                tenant_id=sales_user.tenant_id,
                request_type="DISCOUNT",
                reference_type="unit",
                reference_id=project.id,
                requested_by_id=sales_user.id,
                status=ApprovalStatus.PENDING.value,
                reason="Customer requested a discount",
                created_at=NOW - timedelta(hours=4),
            )
        )
        session.commit()

    response = client.get("/api/v1/sales-floor/my-day", headers=_api(client, sales_user.email))
    assert response.status_code == 200, response.text
    data = response.json()
    kinds = [item["kind"] for item in data["items"]]
    assert set(kinds) == {"FOLLOW_UP", "VISIT", "FIRST_RESPONSE", "CONVERSATION", "APPROVAL"}
    assert kinds[0] == "FOLLOW_UP"
    assert kinds[1] == "VISIT"
    assert kinds.index("FIRST_RESPONSE") < kinds.index("CONVERSATION") < kinds.index("APPROVAL")
    assert "Other Lead" not in response.text
    scores = [item["priority_score"] for item in data["items"]]
    assert scores == sorted(scores, reverse=True)
    assert data["items"][0]["urgency"] == "OVERDUE"
    assert data["items"][0]["priority_score"] > data["items"][1]["priority_score"]
    assert all(
        item["project_name"] == "Sales Floor Homes"
        for item in data["items"] if item["kind"] != "APPROVAL"
    )
    assert all(item["reason"] for item in data["items"])
    assert data["promises_included"] is False
    assert "installment_promises" in data["priority_explanation"]


def test_manager_my_day_has_tenant_team_scope_and_buyer_is_forbidden(
    client: TestClient,
    override_db: None,
    manager_user: User,
    sales_user: User,
    buyer_user: User,
) -> None:
    headers = _api(client, manager_user.email)
    assert client.get("/api/v1/sales-floor/my-day", headers=headers).status_code == 200
    buyer_headers = _api(client, buyer_user.email)
    for path in (
        "/api/v1/sales-floor/my-day",
        "/api/v1/sales-floor/war-room",
    ):
        response = client.get(path, headers=buyer_headers)
        assert response.status_code == 403, response.text
    response = client.get(
        "/api/v1/sales-floor/lead-routing/suggest",
        params={"lead_id": sales_user.id},
        headers=buyer_headers,
    )
    assert response.status_code == 403


def test_war_room_counts_cancelled_and_cross_tenant_exclusions(
    client: TestClient,
    override_db: None,
    test_session_factory: Callable[..., object],
    manager_user: User,
    sales_user: User,
    user_factory: Callable[..., User],
) -> None:
    other_tenant = Tenant(slug="sales-floor-other", name="Other organization")
    with test_session_factory() as session:
        session.add(other_tenant)
        session.flush()
        other_exec = user_factory(
            role=RoleName.SALES_EXECUTIVE,
            email="sales-floor-foreign@example.com",
            tenant=other_tenant,
        )
        project = _project(sales_user.tenant_id, manager_user.id, "War Room")
        foreign_project = _project(other_tenant.id, other_exec.id, "Foreign Project")
        session.add_all([project, foreign_project])
        session.flush()
        leads = [
            _lead(sales_user.tenant_id, project.id, name=f"War Lead {i}", created_at=NOW - timedelta(hours=2))
            for i in range(3)
        ]
        foreign_lead = _lead(other_tenant.id, foreign_project.id, name="Foreign Lead", created_at=NOW)
        session.add_all([*leads, foreign_lead])
        session.flush()
        session.add(_assignment(sales_user.tenant_id, leads[0], sales_user, manager_user))
        slot = VisitSlot(
            tenant_id=sales_user.tenant_id,
            project_id=project.id,
            start_time=DAY_START + timedelta(hours=10),
            end_time=DAY_START + timedelta(hours=11),
        )
        foreign_slot = VisitSlot(
            tenant_id=other_tenant.id,
            project_id=foreign_project.id,
            start_time=DAY_START + timedelta(hours=12),
            end_time=DAY_START + timedelta(hours=13),
        )
        session.add_all([slot, foreign_slot])
        session.flush()
        for lead, status, target_slot in [
            (leads[0], BookingStatus.CONFIRMED.value, slot),
            (leads[1], BookingStatus.CANCELLED.value, slot),
            (foreign_lead, BookingStatus.CONFIRMED.value, foreign_slot),
        ]:
            session.add(
                Booking(
                    tenant_id=lead.tenant_id,
                    slot_id=target_slot.id,
                    lead_id=lead.id,
                    project_id=lead.project_id,
                    buyer_id=manager_user.id if lead.tenant_id == sales_user.tenant_id else other_exec.id,
                    executive_id=sales_user.id if lead.tenant_id == sales_user.tenant_id else other_exec.id,
                    status=status,
                    created_at=NOW,
                )
            )
        for request_type, status in [
            ("DISCOUNT", ApprovalStatus.PENDING.value),
            ("DISCOUNT", ApprovalStatus.APPROVED.value),
            ("OTHER", ApprovalStatus.PENDING.value),
        ]:
            session.add(
                ApprovalRequest(
                    tenant_id=sales_user.tenant_id,
                    request_type=request_type,
                    reference_type="unit",
                    reference_id=project.id,
                    status=status,
                    reason="Fixture",
                    requested_by_id=sales_user.id,
                )
            )
        session.commit()

    response = client.get("/api/v1/sales-floor/war-room", headers=_api(client, manager_user.email))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["new_leads_total"] == 3
    assert data["unassigned_leads_count"] == 2
    assert data["pending_discount_approvals"] == 1
    assert data["visits_today"] == 1
    assert data["bookings_created_today"] == 1
    assert len(data["executive_activity"]) == 1
    assert data["executive_activity"][0]["visits_today"] == 1
    assert data["project_funnels"][0]["today"] == {"enquiries": 3, "visits": 1, "bookings": 1}
    assert data["project_funnels"][0]["seven_day_average"]["enquiries"] == round(3 / 7, 2)


def test_lead_routing_is_deterministic_language_aware_and_tenant_scoped(
    client: TestClient,
    override_db: None,
    test_session_factory: Callable[..., object],
    manager_user: User,
    sales_user: User,
    user_factory: Callable[..., User],
) -> None:
    second = user_factory(role=RoleName.SALES_EXECUTIVE, email="sales-floor-second@example.com")
    inactive = user_factory(
        role=RoleName.SALES_EXECUTIVE, email="sales-floor-inactive@example.com", is_active=False
    )
    with test_session_factory() as session:
        project = _project(sales_user.tenant_id, manager_user.id, "Routing")
        session.add(project)
        session.flush()
        target = _lead(
            sales_user.tenant_id, project.id, name="Kannada Lead", created_at=NOW, language="kn"
        )
        old = _lead(sales_user.tenant_id, project.id, name="Prior Lead", created_at=NOW - timedelta(days=5))
        busy = _lead(sales_user.tenant_id, project.id, name="Busy Lead", created_at=NOW - timedelta(days=4))
        session.add_all([target, old, busy])
        session.flush()
        session.add_all(
            [
                _assignment(sales_user.tenant_id, old, sales_user, manager_user, unassigned_at=NOW - timedelta(days=1)),
                _assignment(sales_user.tenant_id, busy, second, manager_user),
                _assignment(sales_user.tenant_id, target, inactive, manager_user, unassigned_at=NOW),
            ]
        )
        session.commit()

    headers = _api(client, manager_user.email)
    response = client.get(
        "/api/v1/sales-floor/lead-routing/suggest", params={"lead_id": target.id}, headers=headers
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["lead"]["language"] == "kn"
    assert data["lead"]["contact_methods"] == ["email", "phone"]
    assert len(data["candidates"]) == 2
    assert data["candidates"][0]["executive_id"] == str(sales_user.id)
    assert data["candidates"][0]["current_open_leads"] == 0
    assert data["candidates"][0]["prior_project_leads"] == 1
    assert data["candidates"][1]["executive_id"] == str(second.id)
    assert data["candidates"][1]["current_open_leads"] == 1
    assert data["language_matching_available"] is False
    assert response.json() == client.get(
        "/api/v1/sales-floor/lead-routing/suggest", params={"lead_id": target.id}, headers=headers
    ).json()
    assert client.get(
        "/api/v1/sales-floor/lead-routing/suggest", params={"lead_id": sales_user.id}, headers=headers
    ).status_code == 404
