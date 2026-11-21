"""Integration tests for the public per-tenant website widget endpoints."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.security import hash_password
from app.modules.leads.models import Lead
from app.modules.omnichannel import repository
from app.modules.omnichannel.models import ChannelType
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD


@pytest.fixture()
def widget_env(
    override_db: None,
    test_session_factory: sessionmaker[Session],
) -> dict:
    """A tenant with an active project, admin, and visitor context."""

    with test_session_factory() as session:
        slug = f"site-{uuid4().hex[:8]}"
        tenant = Tenant(slug=slug, name="Widget Realty", brand_name="Widget Realty")
        session.add(tenant)
        session.flush()
        role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one_or_none()
        if role is None:
            role = Role(name=RoleName.ADMIN.value)
            session.add(role)
            session.flush()
        admin = User(
            tenant_id=tenant.id,
            full_name="Widget Admin",
            email=f"wadmin.{tenant.id.hex[:10]}@widget.example",
            password_hash=hash_password(TEST_PASSWORD),
            role_id=role.id,
            is_active=True,
        )
        session.add(admin)
        session.flush()  # assign admin.id before referencing it in the project FK
        project = Project(
            tenant_id=tenant.id,
            name="Riverfront Residency",
            slug=f"riverfront-{tenant.id.hex[:8]}",
            location="Ahmedabad",
            status=ProjectStatus.ACTIVE.value,
            created_by=admin.id,
            rera_number="PR/GJ/Ahmedabad/Housing/2024/00123",
        )
        session.add(project)
        session.commit()
        return {
            "tenant_id": tenant.id,
            "project_id": project.id,
            "slug": slug,
            "visitor": uuid4().hex,
            "factory": test_session_factory,
        }


def _session(client: TestClient, env: dict, **overrides) -> dict:
    payload = {"visitor_id": env["visitor"], "project_id": str(env["project_id"])}
    payload.update(overrides)
    response = client.post(f"/api/v1/widget/{env['slug']}/session", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


class TestEmbedScript:
    def test_serves_tenant_branded_script(self, client: TestClient, widget_env: dict) -> None:
        response = client.get(f"/api/v1/widget/{widget_env['slug']}/embed.js")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/javascript")
        assert "propflowWidget" in response.text
        assert widget_env["slug"] in response.text

    def test_unknown_tenant_slug_is_404(self, client: TestClient, widget_env: dict) -> None:
        assert client.get("/api/v1/widget/no-such-site/embed.js").status_code == 404

    def test_suspended_tenant_is_404(
        self, client: TestClient, widget_env: dict
    ) -> None:
        with widget_env["factory"]() as db:
            tenant = db.get(Tenant, widget_env["tenant_id"])
            tenant.status = "suspended"
            db.commit()
        assert client.get(f"/api/v1/widget/{widget_env['slug']}/embed.js").status_code == 404


class TestWidgetSession:
    def test_session_returns_token_and_reuses_thread(
        self, client: TestClient, widget_env: dict
    ) -> None:
        first = _session(client, widget_env)
        assert first["widget_token"]
        second = _session(client, widget_env)
        assert second["conversation_id"] == first["conversation_id"]

    def test_foreign_project_id_is_dropped_silently(
        self, client: TestClient, widget_env: dict
    ) -> None:
        session = _session(client, widget_env, project_id=str(uuid4()))
        response = client.post(
            f"/api/v1/widget/{widget_env['slug']}/chat",
            json={"message": "Hello"},
            headers={"Authorization": f"Bearer {session['widget_token']}"},
        )
        assert response.status_code == 200


class TestWidgetChat:
    def test_chat_persists_both_sides(
        self, client: TestClient, widget_env: dict
    ) -> None:
        session = _session(client, widget_env)
        response = client.post(
            f"/api/v1/widget/{widget_env['slug']}/chat",
            json={"message": "What is the RERA number?"},
            headers={"Authorization": f"Bearer {session['widget_token']}"},
        )
        assert response.status_code == 200
        assert response.json()["reply"]
        with widget_env["factory"]() as db:
            conversation = repository.get_conversation(
                db,
                tenant_id=widget_env["tenant_id"],
                conversation_id=UUID(session["conversation_id"]),
                with_messages=True,
            )
            directions = [m.direction for m in conversation.messages]
            assert directions.count("INBOUND") == 1
            assert directions.count("OUTBOUND") == 1
            assert conversation.unread_count == 1

    def test_chat_requires_widget_token(self, client: TestClient, widget_env: dict) -> None:
        response = client.post(
            f"/api/v1/widget/{widget_env['slug']}/chat", json={"message": "hi"}
        )
        assert response.status_code == 401

    def test_tenant_a_token_rejected_on_tenant_b(
        self, client: TestClient, widget_env: dict
    ) -> None:
        session = _session(client, widget_env)
        with widget_env["factory"]() as db:
            other = Tenant(slug=f"other-{uuid4().hex[:6]}", name="Other Realty")
            db.add(other)
            db.commit()
            other_slug = other.slug
        response = client.post(
            f"/api/v1/widget/{other_slug}/chat",
            json={"message": "sneak"},
            headers={"Authorization": f"Bearer {session['widget_token']}"},
        )
        assert response.status_code in (403, 404)


class TestWidgetLeadCapture:
    def test_lead_is_created_and_attached_to_thread(
        self, client: TestClient, widget_env: dict
    ) -> None:
        session = _session(client, widget_env)
        response = client.post(
            f"/api/v1/widget/{widget_env['slug']}/lead",
            json={
                "full_name": "Ravi Kumar",
                "phone": "919812345678",
                "email": "ravi@example.com",
                "consent_to_contact": True,
            },
            headers={"Authorization": f"Bearer {session['widget_token']}"},
        )
        assert response.status_code == 201, response.text
        with widget_env["factory"]() as db:
            lead = db.get(Lead, UUID(response.json()["lead_id"]))
            assert lead.phone == "919812345678"
            assert lead.source == "WEBSITE"
            assert lead.consent_to_contact is True
            assert lead.project_id == widget_env["project_id"]
            conversation = repository.find_thread(
                db,
                tenant_id=widget_env["tenant_id"],
                channel=ChannelType.WEB_CHAT.value,
                external_thread_id=widget_env["visitor"],
            )
            assert conversation.lead_id == lead.id

    def test_consent_is_mandatory(self, client: TestClient, widget_env: dict) -> None:
        session = _session(client, widget_env)
        response = client.post(
            f"/api/v1/widget/{widget_env['slug']}/lead",
            json={
                "full_name": "No Consent",
                "phone": "919800001111",
                "consent_to_contact": False,
            },
            headers={"Authorization": f"Bearer {session['widget_token']}"},
        )
        assert response.status_code == 400
