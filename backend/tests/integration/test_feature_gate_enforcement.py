"""Integration tests proving feature flags actually gate the HTTP surface."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.security import hash_password
from app.modules.operator.feature_models import TenantFeature
from app.modules.omnichannel import repository
from app.modules.omnichannel.models import ChannelConversation, ChannelType
from app.modules.omnichannel.webhooks import parse_simulated_message
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD


def _make_tenant(session: Session) -> tuple[Tenant, User]:
    slug = f"gate-{uuid4().hex[:8]}"
    tenant = Tenant(slug=slug, name="Gate Co")
    session.add(tenant)
    session.flush()
    role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one_or_none()
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    admin = User(
        tenant_id=tenant.id,
        full_name="Gate Admin",
        email=f"gadmin.{tenant.id.hex[:10]}@gate.example",
        password_hash=hash_password(TEST_PASSWORD),
        role_id=role.id,
        is_active=True,
    )
    session.add(admin)
    session.flush()
    project = Project(
        tenant_id=tenant.id,
        name="Gate Tower",
        slug=f"gate-tower-{tenant.id.hex[:8]}",
        location="Surat",
        status=ProjectStatus.ACTIVE.value,
        created_by=admin.id,
    )
    session.add(project)
    session.commit()
    return tenant, admin


def _login(client: TestClient, admin: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"email": admin.email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class TestInboxGate:
    def test_disabled_inbox_returns_404(
        self,
        client: TestClient,
        override_db: None,
        test_session_factory: sessionmaker[Session],
    ) -> None:
        with test_session_factory() as db:
            _tenant, admin = _make_tenant(db)
        headers = _login(client, admin)
        # omnichannel_inbox defaults to OFF for new tenants.
        response = client.get("/api/v1/omnichannel/inbox", headers=headers)
        assert response.status_code == 404

    def test_enabled_inbox_returns_200(
        self,
        client: TestClient,
        override_db: None,
        test_session_factory: sessionmaker[Session],
    ) -> None:
        with test_session_factory() as db:
            tenant, admin = _make_tenant(db)
            db.add(TenantFeature(tenant_id=tenant.id, feature="omnichannel_inbox", enabled=True))
            db.commit()
        headers = _login(client, admin)
        response = client.get("/api/v1/omnichannel/inbox", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 0


class TestWebhookGate:
    def test_disabled_channel_rejects_webhook(
        self,
        client: TestClient,
        override_db: None,
        test_session_factory: sessionmaker[Session],
    ) -> None:
        with test_session_factory() as db:
            tenant, _admin = _make_tenant(db)
            # Inbox enabled but the specific channel disabled.
            db.add(TenantFeature(tenant_id=tenant.id, feature="omnichannel_inbox", enabled=True))
            db.commit()
            tenant_id = tenant.id
        response = client.post(
            f"/api/v1/webhooks/channels/{tenant_id}/WHATSAPP",
            json={"text": "hi"},
        )
        assert response.status_code == 404


class TestWidgetGate:
    def test_disabled_widget_blocks_embed_and_session(
        self,
        client: TestClient,
        override_db: None,
        test_session_factory: sessionmaker[Session],
    ) -> None:
        with test_session_factory() as db:
            tenant, _admin = _make_tenant(db)
            db.add(TenantFeature(tenant_id=tenant.id, feature="web_widget", enabled=False))
            db.commit()
            slug = tenant.slug
        assert client.get(f"/api/v1/widget/{slug}/embed.js").status_code == 404
        assert client.post(f"/api/v1/widget/{slug}/session", json={}).status_code == 404
