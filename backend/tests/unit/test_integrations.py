"""Unit coverage for encrypted integration connection administration and health."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.security import hash_password
from app.modules.integrations.schemas import MetaPageConnectionUpsert
from app.modules.integrations.service import (
    get_credentials,
    list_connections,
    record_error,
    record_success,
    upsert_meta_page,
)
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD

pytest.importorskip("cryptography", reason="Integration credentials require cryptography.")


@pytest.fixture(autouse=True)
def vault_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptography.fernet import Fernet

    from app.core.config import get_settings

    monkeypatch.setattr(
        get_settings(), "encryption_key", Fernet.generate_key().decode(), raising=False
    )


def _fixture(session: Session) -> tuple[Tenant, User, Project]:
    tenant = Tenant(slug=f"integration-{uuid4().hex[:8]}", name="Integration Co")
    session.add(tenant)
    session.flush()
    role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one_or_none()
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    admin = User(
        tenant_id=tenant.id,
        full_name="Integration Admin",
        email=f"admin.{tenant.id.hex[:8]}@integration.example",
        password_hash=hash_password(TEST_PASSWORD),
        role_id=role.id,
        is_active=True,
    )
    session.add(admin)
    session.flush()
    project = Project(
        tenant_id=tenant.id,
        name="Integration Tower",
        slug=f"integration-{tenant.id.hex[:8]}",
        location="Hyderabad",
        status=ProjectStatus.ACTIVE.value,
        created_by=admin.id,
    )
    session.add(project)
    session.commit()
    return tenant, admin, project


def test_connection_encrypts_credentials_and_reports_health(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, project = _fixture(session)
        connection = upsert_meta_page(
            session,
            actor=admin,
            page_id="page-health",
            payload=MetaPageConnectionUpsert(
                project_id=project.id,
                access_token="private-page-token",
                app_secret="private-app-secret",
                webhook_verify_token="subscription-token",
            ),
        )
        assert "private-page-token" not in connection.credentials_ciphertext
        assert get_credentials(connection) == {
            "access_token": "private-page-token",
            "app_secret": "private-app-secret",
        }
        record_error(session, connection, "Graph API unavailable")
        assert connection.last_error == "Graph API unavailable"
        assert connection.last_error_at is not None
        record_success(session, connection)
        assert connection.last_success_at is not None
        assert connection.last_error is None
        assert connection.last_error_at is None
        assert list_connections(session, tenant_id=tenant.id) == [connection]
