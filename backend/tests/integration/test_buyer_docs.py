"""BuyerVault: staff uploads, verification, requests, isolation, and migration."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.modules.auth.security import hash_password
from app.modules.buyer_docs import service, storage
from app.modules.buyer_docs.models import (
    BuyerDocumentCategory,
    BuyerDocumentStatus,
    DocumentRequest,
    DocumentRequestStatus,
)
from app.modules.customers.models import Contact, ContactStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.exceptions import InsufficientPermissionsError
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD

PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)
STAFF_ROLES = (RoleName.ADMIN.value, RoleName.SALES_EXECUTIVE.value)


@pytest.fixture(autouse=True)
def buyer_docs_storage(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("BUYER_DOCS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        yield tmp_path
    finally:
        get_settings.cache_clear()


def _fixture(session: Session):
    tenant = Tenant(slug=f"vault-{uuid4().hex[:8]}", name="Vault Co")
    session.add(tenant)
    session.flush()
    role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one_or_none()
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    admin = User(
        tenant_id=tenant.id,
        full_name="Admin",
        email=f"vault.{tenant.id.hex[:8]}@example.com",
        password_hash=hash_password(TEST_PASSWORD),
        role_id=role.id,
        is_active=True,
    )
    session.add(admin)
    session.flush()
    session.refresh(admin)
    contact = Contact(
        tenant_id=tenant.id,
        canonical_key=f"uuid:{uuid4()}",
        display_name="Buyer One",
        status=ContactStatus.ACTIVE.value,
    )
    session.add(contact)
    session.commit()
    return tenant, admin, contact


def _upload(
    session: Session,
    admin: User,
    contact: Contact,
    *,
    category: BuyerDocumentCategory = BuyerDocumentCategory.IDENTITY,
    contents: bytes = PNG_BYTES,
    expiry_date: date | None = None,
):
    return service.upload_document(
        session,
        actor=admin,
        contact_id=contact.id,
        category=category,
        title="Identity proof",
        contents=contents,
        content_type="image/png",
        expiry_date=expiry_date,
    )


def test_upload_creates_submitted_document_and_tenant_file(
    test_session_factory: sessionmaker[Session], tmp_path
) -> None:
    with test_session_factory() as session:
        tenant, admin, contact = _fixture(session)
        document = _upload(session, admin, contact)
        assert document.status == BuyerDocumentStatus.SUBMITTED.value
        assert document.content_sha256 == hashlib.sha256(PNG_BYTES).hexdigest()
        assert document.storage_path.startswith(f"{tenant.id}/")
        assert storage.resolve_path(document.storage_path).read_bytes() == PNG_BYTES
        assert len([path for path in tmp_path.rglob("*") if path.is_file()]) == 1
        assert service.list_documents(session, tenant_id=tenant.id) == [document]


def test_upload_fulfills_matching_open_request(
    test_session_factory: sessionmaker[Session]
) -> None:
    with test_session_factory() as session:
        _tenant, admin, contact = _fixture(session)
        request = service.create_request(
            session,
            actor=admin,
            contact_id=contact.id,
            category=BuyerDocumentCategory.IDENTITY,
            title="Provide identity proof",
        )
        other = service.create_request(
            session,
            actor=admin,
            contact_id=contact.id,
            category=BuyerDocumentCategory.ADDRESS,
            title="Provide address proof",
        )
        _upload(session, admin, contact)
        assert request.status == DocumentRequestStatus.FULFILLED.value
        assert other.status == DocumentRequestStatus.OPEN.value
        assert request.updated_at is not None


@pytest.mark.parametrize("decision", ["VERIFIED", "REJECTED"])
def test_review_decision_sets_review_metadata(
    test_session_factory: sessionmaker[Session], decision: str
) -> None:
    with test_session_factory() as session:
        _tenant, admin, contact = _fixture(session)
        document = _upload(session, admin, contact)
        reviewed = service.review_document(
            session,
            actor=admin,
            document_id=document.id,
            decision=decision,
            review_note="Checked by staff",
        )
        assert reviewed.status == decision
        assert reviewed.reviewed_at is not None
        assert reviewed.verified_by_id == admin.id
        with pytest.raises(HTTPException) as exc:
            service.review_document(
                session, actor=admin, document_id=document.id, decision=decision
            )
        assert exc.value.status_code == 400


def test_upload_rejects_empty_and_bad_type(
    test_session_factory: sessionmaker[Session]
) -> None:
    with test_session_factory() as session:
        tenant, admin, contact = _fixture(session)
        for contents, content_type in ((b"", "image/png"), (PNG_BYTES, "text/html")):
            with pytest.raises(HTTPException) as exc:
                service.upload_document(
                    session,
                    actor=admin,
                    contact_id=contact.id,
                    category=BuyerDocumentCategory.IDENTITY,
                    title="Invalid",
                    contents=contents,
                    content_type=content_type,
                )
            assert exc.value.status_code == 400
        assert service.list_documents(session, tenant_id=tenant.id) == []


def test_upload_rejects_oversize(
    test_session_factory: sessionmaker[Session]
) -> None:
    with test_session_factory() as session:
        tenant, admin, contact = _fixture(session)
        with pytest.raises(HTTPException) as exc:
            service.upload_document(
                session,
                actor=admin,
                contact_id=contact.id,
                category=BuyerDocumentCategory.IDENTITY,
                title="Invalid",
                contents=b"x" * (10 * 1024 * 1024 + 1),
                content_type="application/pdf",
            )
        assert exc.value.status_code == 400
        assert service.list_documents(session, tenant_id=tenant.id) == []


def test_buyer_cannot_upload(
    test_session_factory: sessionmaker[Session]
) -> None:
    with test_session_factory() as session:
        _tenant, admin, contact = _fixture(session)
        buyer = SimpleNamespace(
            id=uuid4(),
            tenant_id=admin.tenant_id,
            role=SimpleNamespace(name=RoleName.BUYER.value),
        )
        with pytest.raises(InsufficientPermissionsError):
            service.upload_document(
                session,
                actor=buyer,
                contact_id=contact.id,
                category=BuyerDocumentCategory.IDENTITY,
                title="Forbidden",
                contents=PNG_BYTES,
                content_type="image/png",
            )


def test_storage_failure_leaves_no_row(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    with test_session_factory() as session:
        tenant, admin, contact = _fixture(session)

        def fail(**_kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(storage, "write_document", fail)
        with pytest.raises(OSError):
            _upload(session, admin, contact)
        assert service.list_documents(session, tenant_id=tenant.id) == []
        assert not any(path.is_file() for path in tmp_path.rglob("*"))


def test_db_failure_removes_new_file_and_rolls_back_request(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    with test_session_factory() as session:
        _tenant, admin, contact = _fixture(session)
        request = service.create_request(
            session,
            actor=admin,
            contact_id=contact.id,
            category=BuyerDocumentCategory.IDENTITY,
            title="Proof",
        )

        def fail_flush(*_args, **_kwargs):
            raise OSError("database unavailable")

        monkeypatch.setattr(session, "flush", fail_flush)
        with pytest.raises(OSError):
            _upload(session, admin, contact)
        assert not any(path.is_file() for path in tmp_path.rglob("*"))
        session.rollback()
        persisted = session.get(DocumentRequest, request.id)
        assert persisted.status == DocumentRequestStatus.OPEN.value


def test_mark_expired_only_expires_past_verified_documents(
    test_session_factory: sessionmaker[Session]
) -> None:
    with test_session_factory() as session:
        tenant, admin, contact = _fixture(session)
        expired = _upload(session, admin, contact, expiry_date=date(2026, 1, 1))
        current = _upload(session, admin, contact, expiry_date=date(2026, 11, 23))
        submitted = _upload(session, admin, contact, expiry_date=date(2025, 1, 1))
        for document in (expired, current):
            service.review_document(
                session, actor=admin, document_id=document.id, decision="VERIFIED"
            )
        assert service.mark_expired(session, now=datetime(2026, 11, 23, tzinfo=UTC)) == 1
        assert expired.status == BuyerDocumentStatus.EXPIRED.value
        assert current.status == BuyerDocumentStatus.VERIFIED.value
        assert submitted.status == BuyerDocumentStatus.SUBMITTED.value
        assert service.mark_expired(session, now=datetime(2026, 11, 23, tzinfo=UTC)) == 0


def test_document_and_request_service_enforce_tenant_and_contact(
    test_session_factory: sessionmaker[Session]
) -> None:
    with test_session_factory() as session:
        tenant, admin, contact = _fixture(session)
        other_tenant = Tenant(slug=f"other-{uuid4().hex[:8]}", name="Other")
        session.add(other_tenant)
        session.commit()
        with pytest.raises(HTTPException) as exc:
            service.create_request(
                session,
                actor=admin,
                contact_id=uuid4(),
                category=BuyerDocumentCategory.IDENTITY,
                title="Unknown",
            )
        assert exc.value.status_code == 404
        document = _upload(session, admin, contact)
        assert service.list_documents(session, tenant_id=other_tenant.id) == []
        with pytest.raises(HTTPException) as exc:
            service.list_documents(
                session,
                tenant_id=other_tenant.id,
                actor=admin,
            )
        assert exc.value.status_code == 404
        with pytest.raises(HTTPException) as exc:
            service.review_document(
                session,
                actor=SimpleNamespace(
                    id=admin.id, tenant_id=other_tenant.id, role=admin.role
                ),
                document_id=document.id,
                decision="VERIFIED",
            )
        assert exc.value.status_code == 404


def test_create_list_cancel_request_and_buyer_403(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    buyer = user_factory(role=RoleName.BUYER)
    headers = auth_headers(admin.email)
    buyer_headers = auth_headers(buyer.email)
    with test_session_factory() as session:
        contact = Contact(
            tenant_id=admin.tenant_id,
            canonical_key=f"uuid:{uuid4()}",
            display_name="API buyer",
            status=ContactStatus.ACTIVE.value,
        )
        session.add(contact)
        session.commit()
        contact_id = str(contact.id)
    response = client.post(
        "/api/v1/buyer-docs/requests",
        headers=headers,
        json={"contact_id": contact_id, "category": "BANK", "title": "Bank statement"},
    )
    assert response.status_code == 201, response.text
    request_id = response.json()["id"]
    assert response.json()["status"] == "OPEN"
    assert client.get("/api/v1/buyer-docs/requests", headers=headers).json()["items"][0]["id"] == request_id
    cancelled = client.post(f"/api/v1/buyer-docs/requests/{request_id}/cancel", headers=headers)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "CANCELLED"
    assert client.get("/api/v1/buyer-docs/requests", headers=buyer_headers).status_code == 403
    upload = client.post(
        f"/api/v1/buyer-docs/documents?contact_id={contact_id}&category=IDENTITY&title=ID",
        headers={**buyer_headers, "content-type": "image/png"},
        content=PNG_BYTES,
    )
    assert upload.status_code == 403


def test_full_api_upload_filter_review_download_and_cross_tenant_404(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    headers = auth_headers(admin.email)
    other_tenant = Tenant(slug=f"other-{uuid4().hex[:8]}", name="Other")
    with test_session_factory() as session:
        session.add(other_tenant)
        session.commit()
        session.refresh(other_tenant)
        contact = Contact(
            tenant_id=admin.tenant_id,
            canonical_key=f"uuid:{uuid4()}",
            display_name="API buyer",
            status=ContactStatus.ACTIVE.value,
        )
        session.add(contact)
        session.commit()
        contact_id = str(contact.id)
    other_admin = user_factory(role=RoleName.ADMIN, tenant=other_tenant)
    other_headers = auth_headers(other_admin.email)
    response = client.post(
        f"/api/v1/buyer-docs/documents?contact_id={contact_id}&category=IDENTITY&title=Passport",
        headers={**headers, "content-type": "image/png"},
        content=PNG_BYTES,
    )
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["status"] == "SUBMITTED"
    assert "storage_path" not in document
    filtered = client.get(
        f"/api/v1/buyer-docs/documents?contact_id={contact_id}&category=IDENTITY&status=SUBMITTED",
        headers=headers,
    )
    assert filtered.status_code == 200
    assert [row["id"] for row in filtered.json()["items"]] == [document["id"]]
    reviewed = client.post(
        f"/api/v1/buyer-docs/documents/{document['id']}/review",
        headers=headers,
        json={"decision": "VERIFIED", "review_note": "Verified"},
    )
    assert reviewed.status_code == 200 and reviewed.json()["reviewed_at"] is not None
    downloaded = client.get(
        f"/api/v1/buyer-docs/documents/{document['id']}/download", headers=headers
    )
    assert downloaded.status_code == 200
    assert downloaded.content == PNG_BYTES
    assert downloaded.headers["x-content-sha256"] == hashlib.sha256(PNG_BYTES).hexdigest()
    cross_tenant = client.get(
        f"/api/v1/buyer-docs/documents/{document['id']}/download", headers=other_headers
    )
    assert cross_tenant.status_code == 404
    cross_tenant = client.post(
        f"/api/v1/buyer-docs/documents/{document['id']}/review",
        headers=other_headers,
        json={"decision": "REJECTED"},
    )
    assert cross_tenant.status_code == 404


def test_storage_rejects_traversal() -> None:
    with pytest.raises(ValueError):
        storage.resolve_path("../outside")
    with pytest.raises(ValueError):
        storage.resolve_path("tenant\\outside")


def test_migration_upgrade_and_downgrade_on_isolated_sqlite() -> None:
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    from app.db.base import Base
    import app.modules.buyer_docs.models  # noqa: F401

    migration_path = next(
        (Path(__file__).parents[2] / "alembic" / "versions").glob("*-e7f8a9b0c1d2_*")
    )
    spec = importlib.util.spec_from_file_location("buyer_docs_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "e7f8a9b0c1d2"
    assert migration.down_revision == "f7a8b9c0d1e2"

    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        with engine.connect() as connection:
            for table_name in ("roles", "tenants", "users", "contacts"):
                Base.metadata.tables[table_name].create(connection)
            context = MigrationContext.configure(connection)
            original_get_bind = Operations.get_bind
            Operations.get_bind = lambda self: connection
            try:
                with Operations.context(context):
                    migration.upgrade()
                    assert {"buyer_documents", "document_requests"} <= set(
                        inspect(connection).get_table_names()
                    )
                    assert "ix_buyer_documents_tenant_status" in {
                        index["name"]
                        for index in inspect(connection).get_indexes("buyer_documents")
                    }
                    migration.downgrade()
                    assert not ({"buyer_documents", "document_requests"} & set(
                        inspect(connection).get_table_names()
                    ))
            finally:
                Operations.get_bind = original_get_bind
    finally:
        engine.dispose()
