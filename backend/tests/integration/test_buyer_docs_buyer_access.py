"""Buyer-portal access layer: /buyer-docs/mine/* scoping and identity resolution.

Staff routes stay unchanged (see test_buyer_docs.py); this file proves the
parallel buyer surface lists/downloads/uploads only for the server-resolved
contact, never for a client-supplied contact, and answers 404 on ambiguity,
absence, and cross-tenant access.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.modules.buyer_docs import service
from app.modules.buyer_docs.models import (
    BuyerDocumentCategory,
    BuyerDocumentStatus,
    DocumentRequest,
    DocumentRequestStatus,
)
from app.modules.customers.models import (
    Contact,
    ContactMethod,
    ContactMethodKind,
    ContactStatus,
    VerificationState,
)
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName

PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


@pytest.fixture(autouse=True)
def buyer_docs_storage(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("BUYER_DOCS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        yield tmp_path
    finally:
        get_settings.cache_clear()


def _contact_with_email(session: Session, *, tenant_id: UUID, email: str) -> Contact:
    """Direct ORM contact whose EMAIL method matches a buyer account email."""
    contact = Contact(
        tenant_id=tenant_id,
        canonical_key=f"uuid:{uuid4()}",
        display_name=email,
        status=ContactStatus.ACTIVE.value,
    )
    session.add(contact)
    session.flush()
    session.add(
        ContactMethod(
            tenant_id=tenant_id,
            contact_id=contact.id,
            kind=ContactMethodKind.EMAIL.value,
            value=email,
            normalized_value=email.lower(),
            verification_state=VerificationState.UNVERIFIED.value,
            provenance={},
            is_primary=True,
        )
    )
    session.commit()
    session.refresh(contact)
    return contact


def test_resolve_buyer_contact_by_email_phone_and_ambiguity(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant = Tenant(slug=f"resolve-{uuid4().hex[:8]}", name="Resolve Co")
        session.add(tenant)
        session.flush()
        by_email = _contact_with_email(
            session, tenant_id=tenant.id, email="Buyer.Email@example.com"
        )
        by_phone = Contact(
            tenant_id=tenant.id,
            canonical_key=f"uuid:{uuid4()}",
            display_name="Phone buyer",
            status=ContactStatus.ACTIVE.value,
        )
        session.add(by_phone)
        session.flush()
        session.add(
            ContactMethod(
                tenant_id=tenant.id,
                contact_id=by_phone.id,
                kind=ContactMethodKind.PHONE.value,
                value="+91 96115 02119",
                normalized_value="+919611502119",
                verification_state=VerificationState.UNVERIFIED.value,
                provenance={},
                is_primary=True,
            )
        )
        session.commit()

        email_actor = SimpleNamespace(
            tenant_id=tenant.id, email="buyer.email@EXAMPLE.com", phone=None
        )
        assert service.resolve_buyer_contact(session, email_actor) == by_email

        phone_actor = SimpleNamespace(
            tenant_id=tenant.id,
            email=f"nobody-{uuid4().hex[:8]}@example.com",
            phone="+91-96115-02119",
        )
        assert service.resolve_buyer_contact(session, phone_actor) == by_phone

        missing = SimpleNamespace(
            tenant_id=tenant.id, email=f"missing-{uuid4().hex[:8]}@example.com", phone=None
        )
        assert service.resolve_buyer_contact(session, missing) is None

        # Email resolves to one contact, phone to another → ambiguous → None.
        ambiguous = SimpleNamespace(
            tenant_id=tenant.id, email="buyer.email@example.com", phone="+919611502119"
        )
        assert service.resolve_buyer_contact(session, ambiguous) is None

        # The same identity never resolves inside a different tenant.
        foreign = SimpleNamespace(
            tenant_id=uuid4(), email="buyer.email@example.com", phone=None
        )
        assert service.resolve_buyer_contact(session, foreign) is None


def test_buyer_lists_only_own_documents_and_staff_still_lists_all(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    buyer = user_factory(role=RoleName.BUYER, email="portal-list@example.com")
    other_buyer = user_factory(role=RoleName.BUYER, email="portal-other@example.com")
    buyer_headers = auth_headers(buyer.email)
    other_headers = auth_headers(other_buyer.email)
    admin_headers = auth_headers(admin.email)
    with test_session_factory() as session:
        own = _contact_with_email(
            session, tenant_id=buyer.tenant_id, email=buyer.email
        )
        other = _contact_with_email(
            session, tenant_id=other_buyer.tenant_id, email=other_buyer.email
        )
        own_doc = service.upload_document(
            session,
            actor=admin,
            contact_id=own.id,
            category=BuyerDocumentCategory.IDENTITY,
            title="Own identity",
            contents=PNG_BYTES,
            content_type="image/png",
        )
        service.upload_document(
            session,
            actor=admin,
            contact_id=other.id,
            category=BuyerDocumentCategory.ADDRESS,
            title="Other address",
            contents=PNG_BYTES,
            content_type="image/png",
        )
        own_id, other_id = own.id, other.id

    listing = client.get("/api/v1/buyer-docs/mine/documents", headers=buyer_headers)
    assert listing.status_code == 200, listing.text
    assert [row["id"] for row in listing.json()["items"]] == [str(own_doc.id)]
    assert listing.json()["total"] == 1

    other_listing = client.get("/api/v1/buyer-docs/mine/documents", headers=other_headers)
    assert [row["title"] for row in other_listing.json()["items"]] == ["Other address"]

    staff_listing = client.get(
        f"/api/v1/buyer-docs/documents?contact_id={own_id}", headers=admin_headers
    )
    assert staff_listing.status_code == 200
    assert [row["id"] for row in staff_listing.json()["items"]] == [str(own_doc.id)]

    # A buyer-provided contact_id query param is not declared, so FastAPI
    # ignores it and the listing stays scoped to the resolved contact.
    smuggled = client.get(
        f"/api/v1/buyer-docs/mine/documents?contact_id={other_id}", headers=buyer_headers
    )
    assert smuggled.status_code == 200
    assert [row["id"] for row in smuggled.json()["items"]] == [str(own_doc.id)]


def test_buyer_download_scoping_other_contact_and_cross_tenant_404(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    buyer = user_factory(role=RoleName.BUYER, email="portal-download@example.com")
    other_buyer = user_factory(role=RoleName.BUYER, email="portal-stranger@example.com")
    other_tenant = Tenant(slug=f"other-{uuid4().hex[:8]}", name="Other")
    with test_session_factory() as session:
        session.add(other_tenant)
        session.commit()
    outsider = user_factory(role=RoleName.BUYER, tenant=other_tenant, email="outsider@example.com")
    buyer_headers = auth_headers(buyer.email)
    outsider_headers = auth_headers(outsider.email)
    with test_session_factory() as session:
        own = _contact_with_email(session, tenant_id=buyer.tenant_id, email=buyer.email)
        other = _contact_with_email(
            session, tenant_id=other_buyer.tenant_id, email=other_buyer.email
        )
        own_doc = service.upload_document(
            session,
            actor=admin,
            contact_id=own.id,
            category=BuyerDocumentCategory.IDENTITY,
            title="Own file",
            contents=PNG_BYTES,
            content_type="image/png",
        )
        other_doc = service.upload_document(
            session,
            actor=admin,
            contact_id=other.id,
            category=BuyerDocumentCategory.BANK,
            title="Not yours",
            contents=PNG_BYTES,
            content_type="image/png",
        )
        own_doc_id, other_doc_id = str(own_doc.id), str(other_doc.id)

    ok = client.get(
        f"/api/v1/buyer-docs/mine/documents/{own_doc_id}/download", headers=buyer_headers
    )
    assert ok.status_code == 200 and ok.content == PNG_BYTES
    assert ok.headers["x-content-sha256"] == hashlib.sha256(PNG_BYTES).hexdigest()
    assert ok.headers["x-content-type-options"] == "nosniff"

    not_mine = client.get(
        f"/api/v1/buyer-docs/mine/documents/{other_doc_id}/download", headers=buyer_headers
    )
    assert not_mine.status_code == 404
    ghost = client.get(
        f"/api/v1/buyer-docs/mine/documents/{uuid4()}/download", headers=buyer_headers
    )
    assert ghost.status_code == 404
    cross_tenant = client.get(
        f"/api/v1/buyer-docs/mine/documents/{own_doc_id}/download", headers=outsider_headers
    )
    assert cross_tenant.status_code == 404


def test_buyer_upload_fulfills_open_request_and_ignores_client_contact(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    buyer = user_factory(role=RoleName.BUYER, email="portal-upload@example.com")
    buyer_headers = auth_headers(buyer.email)
    with test_session_factory() as session:
        contact = _contact_with_email(session, tenant_id=buyer.tenant_id, email=buyer.email)
        decoy = Contact(
            tenant_id=buyer.tenant_id,
            canonical_key=f"uuid:{uuid4()}",
            display_name="Decoy",
            status=ContactStatus.ACTIVE.value,
        )
        session.add(decoy)
        session.commit()
        request = service.create_request(
            session,
            actor=admin,
            contact_id=contact.id,
            category=BuyerDocumentCategory.BANK,
            title="Bank statement please",
        )
        unrelated = service.create_request(
            session,
            actor=admin,
            contact_id=decoy.id,
            category=BuyerDocumentCategory.BANK,
            title="Decoy request",
        )
        contact_id, decoy_id = contact.id, decoy.id
        request_id, unrelated_id = request.id, unrelated.id

    open_requests = client.get("/api/v1/buyer-docs/mine/requests", headers=buyer_headers)
    assert open_requests.status_code == 200
    assert [row["id"] for row in open_requests.json()["items"]] == [str(request_id)]

    upload = client.post(
        f"/api/v1/buyer-docs/mine/documents?category=BANK&title=My statement"
        f"&contact_id={decoy_id}",
        headers={**buyer_headers, "content-type": "application/pdf"},
        content=b"%PDF-1.4 test bytes",
    )
    # contact_id is not a declared param and is ignored: the document still
    # lands on the server-resolved contact, never the decoy.
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert body["contact_id"] == str(contact_id)
    assert body["status"] == BuyerDocumentStatus.SUBMITTED.value
    assert body["content_type"] == "application/pdf"
    assert "storage_path" not in body

    with test_session_factory() as session:
        assert session.get(DocumentRequest, request_id).status == DocumentRequestStatus.FULFILLED.value
        assert session.get(DocumentRequest, unrelated_id).status == DocumentRequestStatus.OPEN.value
    after = client.get("/api/v1/buyer-docs/mine/requests", headers=buyer_headers)
    assert after.json()["items"] == []


def test_buyer_upload_rejects_bad_payloads(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> None:
    buyer = user_factory(role=RoleName.BUYER, email="portal-guards@example.com")
    buyer_headers = auth_headers(buyer.email)
    with test_session_factory() as session:
        _contact_with_email(session, tenant_id=buyer.tenant_id, email=buyer.email)
    for payload, content_type in ((b"", "image/png"), (PNG_BYTES, "text/html")):
        response = client.post(
            "/api/v1/buyer-docs/mine/documents?category=IDENTITY&title=Bad",
            headers={**buyer_headers, "content-type": content_type},
            content=payload,
        )
        assert response.status_code == 400
    oversize = client.post(
        "/api/v1/buyer-docs/mine/documents?category=IDENTITY&title=Too big",
        headers={**buyer_headers, "content-type": "application/pdf"},
        content=b"x" * (10 * 1024 * 1024 + 1),
    )
    assert oversize.status_code == 400
    assert client.get("/api/v1/buyer-docs/mine/documents", headers=buyer_headers).json()["items"] == []


def test_unresolvable_buyer_gets_404_on_every_mine_route(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    user_factory,
    auth_headers,
) -> None:
    buyer = user_factory(role=RoleName.BUYER, email="portal-nobody@example.com")
    buyer_headers = auth_headers(buyer.email)
    assert client.get("/api/v1/buyer-docs/mine/documents", headers=buyer_headers).status_code == 404
    assert client.get("/api/v1/buyer-docs/mine/requests", headers=buyer_headers).status_code == 404
    assert (
        client.get(
            f"/api/v1/buyer-docs/mine/documents/{uuid4()}/download", headers=buyer_headers
        ).status_code
        == 404
    )
    upload = client.post(
        "/api/v1/buyer-docs/mine/documents?category=IDENTITY&title=Ghost",
        headers={**buyer_headers, "content-type": "image/png"},
        content=PNG_BYTES,
    )
    assert upload.status_code == 404


def test_staff_can_use_mine_and_staff_only_routes_reject_buyers(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> None:
    admin = user_factory(role=RoleName.ADMIN, email="portal-staff@example.com")
    buyer = user_factory(role=RoleName.BUYER, email="portal-regular@example.com")
    admin_headers = auth_headers(admin.email)
    buyer_headers = auth_headers(buyer.email)
    with test_session_factory() as session:
        contact = _contact_with_email(session, tenant_id=admin.tenant_id, email=admin.email)
        contact_id = contact.id
    staff_upload = client.post(
        "/api/v1/buyer-docs/mine/documents?category=AGREEMENT&title=Staff self upload",
        headers={**admin_headers, "content-type": "image/png"},
        content=PNG_BYTES,
    )
    assert staff_upload.status_code == 201, staff_upload.text
    assert staff_upload.json()["contact_id"] == str(contact_id)
    staff_list = client.get("/api/v1/buyer-docs/mine/documents", headers=admin_headers)
    assert staff_list.status_code == 200 and staff_list.json()["total"] == 1

    # Legacy staff surface remains locked for buyers.
    assert client.get("/api/v1/buyer-docs/documents", headers=buyer_headers).status_code == 403
    assert client.get("/api/v1/buyer-docs/requests", headers=buyer_headers).status_code == 403
    staff_create = client.post(
        "/api/v1/buyer-docs/requests",
        headers=buyer_headers,
        json={"contact_id": str(contact_id), "category": "BANK", "title": "Nope"},
    )
    assert staff_create.status_code == 403


def test_buyer_service_download_rejects_foreign_contact(
    test_session_factory: sessionmaker[Session], user_factory
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    with test_session_factory() as session:
        own = _contact_with_email(
            session, tenant_id=admin.tenant_id, email=f"owner-{uuid4().hex[:6]}@example.com"
        )
        other = _contact_with_email(
            session, tenant_id=admin.tenant_id, email=f"other-{uuid4().hex[:6]}@example.com"
        )
        document = service.upload_document(
            session,
            actor=admin,
            contact_id=other.id,
            category=BuyerDocumentCategory.IDENTITY,
            title="Other's file",
            contents=PNG_BYTES,
            content_type="image/png",
        )
        with pytest.raises(HTTPException) as exc:
            service.get_buyer_document_for_download(
                session, contact=own, document_id=document.id
            )
        assert exc.value.status_code == 404
        loaded, path = service.get_buyer_document_for_download(
            session, contact=other, document_id=document.id
        )
        assert loaded.id == document.id
        assert path.read_bytes() == PNG_BYTES
        requests = service.list_buyer_open_requests(session, contact=other)
        assert requests == []
