"""Document engine integration: issuance, evidence, storage, isolation, and API."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.modules.documents import repository as document_repository
from app.modules.documents import service as document_service
from app.modules.documents import storage
from app.modules.documents.models import Document, DocumentStatus, DocumentTemplate, DocumentTemplateKey
from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.postsales import service as postsales_service
from app.modules.postsales.models import Installment, Receipt, ReceiptChannel
from app.modules.postsales.schemas import (
    InstallmentSpec,
    PaymentPlanCreateRequest,
    PaymentPlanType,
    ReceiptCreateRequest,
    SaleBookingCreateRequest,
)
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from tests.support import TEST_PASSWORD


def _login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _fixture(session: Session, *, slug: str | None = None) -> tuple[Tenant, User, Project, Lead]:
    tenant = Tenant(
        slug=slug or f"doc-{uuid4().hex[:8]}", name="Document Realty",
        theme_json={
            "legal_entity_name": "Document Realty Private Limited",
            "legal_entity_address": "12 Example Road, Pune",
            "support_contact": "accounts@example.test",
            "bank": {"name": "Example Bank", "account_name": "Document Realty", "account_number": "1234567890123456", "ifsc": "EXAM0001234"},
        },
    )
    session.add(tenant)
    session.flush()
    from app.modules.users.models import Role

    role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one_or_none()
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    admin = User(
        tenant_id=tenant.id, full_name="Finance Admin", email=f"admin.{tenant.id.hex[:8]}@example.test",
        password_hash="test-not-a-password", role_id=role.id, is_active=True,
    )
    session.add(admin)
    session.flush()
    project = Project(
        tenant_id=tenant.id, name="Document Heights", slug=f"heights-{tenant.id.hex[:8]}",
        location="Pune", status=ProjectStatus.ACTIVE.value, created_by=admin.id,
        rera_number="P52100000000",
    )
    session.add(project)
    session.flush()
    lead = Lead(
        tenant_id=tenant.id, full_name="Buyer One", email=f"buyer.{tenant.id.hex[:8]}@example.test",
        phone="+919800000001", project_id=project.id, source=LeadSource.WEBSITE.value,
        status=LeadStatus.CONVERTED.value, consent_to_contact=True,
    )
    session.add(lead)
    session.commit()
    return tenant, admin, project, lead


def _installment_and_receipt(session: Session, admin: User, lead: Lead) -> tuple[Installment, Receipt]:
    booking = postsales_service.create_booking(
        session, actor=admin,
        payload=SaleBookingCreateRequest(
            lead_id=lead.id, unit_number="B-1201", configuration="3 BHK",
            consideration_paise=123456789,
        ),
    )
    plan = postsales_service.create_plan(
        session, actor=admin, booking_id=booking.id,
        payload=PaymentPlanCreateRequest(
            name="Single milestone", plan_type=PaymentPlanType.TIME_LINKED,
            installments=[InstallmentSpec(
                milestone="Slab completion", amount_paise=123456789,
                due_on=date(2026, 12, 15),
            )],
        ),
    )
    installment = plan.installments[0]
    receipt = postsales_service.record_receipt(
        session, actor=admin,
        payload=ReceiptCreateRequest(
            installment_id=installment.id, amount_paise=23456789,
            channel=ReceiptChannel.UPI, reference="UTR-12345",
        ),
    )
    return installment, receipt


def _seed_context(session: Session):
    tenant, admin, _project, lead = _fixture(session)
    installment, receipt = _installment_and_receipt(session, admin, lead)
    return tenant, admin, installment, receipt


def test_demand_letter_materializes_real_values_and_is_idempotent(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("DOCUMENTS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with test_session_factory() as session:
            tenant, admin, installment, _receipt = _seed_context(session)
            first = document_service.issue_demand_letter(session, actor=admin, installment_id=installment.id)
            second = document_service.issue_demand_letter(session, actor=admin, installment_id=installment.id)
            assert first.id == second.id
            assert first.document_number == "DOC-DEMAND-000001"
            assert first.payload_snapshot["unit_code"] == "B-1201"
            assert first.payload_snapshot["milestone"] == "Slab completion"
            assert first.payload_snapshot["due_date"] == "15 Dec 2026"
            assert first.payload_snapshot["amount"] == "Rs. 12,34,567.89"
            assert first.payload_snapshot["collected_paise"] == 23456789
            assert first.payload_snapshot["outstanding_paise"] == 100000000
            assert first.payload_snapshot["bank_account_number"] == "XXXX3456"
            assert "1234567890123456" not in str(first.payload_snapshot)
            assert not first.storage_path.startswith("/")
            assert "storage_path" not in str(first.payload_snapshot)
            pdf = storage.resolve_path(first.storage_path).read_bytes()
            assert hashlib.sha256(pdf).hexdigest() == first.content_sha256
            assert len(list(tmp_path.rglob("*.pdf"))) == 1
            assert b"B-1201" in pdf and b"Slab completion" in pdf and b"Rs. 12,34,567.89" in pdf

            updated = postsales_service.send_demand_letter(session, actor=admin, installment_id=installment.id)
            assert isinstance(updated, Installment)
            assert updated.__dict__["demand_letter_document"].id == first.id
            assert updated.demand_letter_sent_at is not None
    finally:
        get_settings.cache_clear()


def test_new_template_version_uses_max_not_count_and_receipt_document(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("DOCUMENTS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with test_session_factory() as session:
            tenant, admin, installment, receipt = _seed_context(session)
            first = document_service.issue_demand_letter(session, actor=admin, installment_id=installment.id)
            # A high existing sequence proves MAX allocation, not COUNT.
            session.add(Document(
                tenant_id=tenant.id, kind="DEMAND_LETTER", reference_type="installment",
                reference_id=uuid4(), template_version=99, document_number="DOC-DEMAND-000042",
                status="ISSUED", storage_path="legacy/not-used.pdf", content_sha256="a" * 64,
                payload_snapshot={},
            ))
            session.commit()
            session.add(DocumentTemplate(
                tenant_id=tenant.id, key=DocumentTemplateKey.DEMAND_LETTER.value,
                version=2, subject="Corrected demand {unit_code}",
                body_template="Pay {outstanding} for {unit_code} by {due_date}.",
                is_active=True, created_by=admin.id,
            ))
            session.commit()
            second = document_service.issue_demand_letter(session, actor=admin, installment_id=installment.id)
            assert second.id != first.id
            assert second.template_version == 2
            assert second.document_number == "DOC-DEMAND-000043"

            receipt_doc = document_service.issue_receipt_pdf(session, actor=admin, receipt_id=receipt.id)
            assert receipt_doc.document_number == "DOC-RECEIPT-000001"
            assert receipt_doc.payload_snapshot["receipt_number"] == "RCPT-000001"
            assert receipt_doc.payload_snapshot["amount"] == "Rs. 2,34,567.89"
            assert b"UTR-12345" in storage.resolve_path(receipt_doc.storage_path).read_bytes()
    finally:
        get_settings.cache_clear()


def test_integrity_conflict_cleans_orphan_file(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("DOCUMENTS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with test_session_factory() as session:
            _tenant, admin, installment, _receipt = _seed_context(session)
            # Force the IntegrityError branch (e.g. a concurrent winner committed
            # first elsewhere); the PDF written just before the DB insert must
            # not be left orphaned by the rollback path.
            original_commit = session.commit
            calls = 0

            def conflict_once():
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise IntegrityError("INSERT", {}, Exception("duplicate document number"))
                return original_commit()

            monkeypatch.setattr(session, "commit", conflict_once)
            with pytest.raises(HTTPException) as conflict:
                document_service.issue_demand_letter(session, actor=admin, installment_id=installment.id)
            assert conflict.value.status_code == 409
            assert not list(tmp_path.rglob("*.pdf"))
            session.expire_all()
            assert session.scalar(select(func.count()).select_from(Document)) == 0
    finally:
        get_settings.cache_clear()


def test_storage_failure_leaves_no_issued_row_or_file(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("DOCUMENTS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with test_session_factory() as session:
            _tenant, admin, installment, _receipt = _seed_context(session)

            def fail_write(**_kwargs):
                raise OSError("simulated disk failure")

            monkeypatch.setattr(storage, "write_pdf", fail_write)
            with pytest.raises(OSError, match="simulated disk failure"):
                document_service.issue_demand_letter(session, actor=admin, installment_id=installment.id)
            session.expire_all()
            assert session.scalar(select(func.count()).select_from(Document)) == 0
            assert not list(tmp_path.rglob("*.pdf"))
    finally:
        get_settings.cache_clear()


def test_void_preserves_evidence_and_download_access_rules(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("DOCUMENTS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with test_session_factory() as session:
            tenant_a, admin_a, installment_a, _receipt_a = _seed_context(session)
            document = document_service.issue_demand_letter(session, actor=admin_a, installment_id=installment_a.id)
            tenant_b, admin_b, _installment_b, _receipt_b = _seed_context(session)
            assert document_repository.get_document(session, document.id, tenant_id=tenant_b.id) is None

            from fastapi import HTTPException
            with pytest.raises(HTTPException) as cross_tenant:
                document_service.get_document_for_download(session, document.id, tenant_id=tenant_b.id)
            assert cross_tenant.value.status_code == 404

            voided = document_service.mark_void(
                session, actor=admin_a, document_id=document.id, reason="Superseded by corrected demand"
            )
            assert voided.status == DocumentStatus.VOIDED.value
            assert voided.void_reason == "Superseded by corrected demand"
            assert storage.resolve_path(document.storage_path).is_file()
            with pytest.raises(HTTPException) as gone:
                document_service.get_document_for_download(session, document.id, tenant_id=tenant_a.id)
            assert gone.value.status_code == 410
            assert "Superseded" in gone.value.detail
    finally:
        get_settings.cache_clear()


def test_document_api_download_hash_proof_void_and_cross_tenant_404(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    user_factory: Callable[..., User],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("DOCUMENTS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with test_session_factory() as session:
            tenant_a = Tenant(
                slug="doc-api-a", name="Doc API A",
                theme_json={
                    "legal_entity_name": "Doc API A Private Limited",
                    "bank": {"name": "Example Bank", "account_name": "Doc API A", "account_number": "1234567890123456", "ifsc": "EXAM0001234"},
                },
            )
            tenant_b = Tenant(slug="doc-api-b", name="Doc API B")
            session.add_all([tenant_a, tenant_b])
            session.flush()
            admin_a = user_factory(role=RoleName.ADMIN, tenant=tenant_a, email="admin-a@doc.example")
            user_factory(role=RoleName.SALES_EXECUTIVE, tenant=tenant_a, email="sales-a@doc.example")
            user_factory(role=RoleName.BUYER, tenant=tenant_a, email="buyer-a@doc.example")
            user_factory(role=RoleName.ADMIN, tenant=tenant_b, email="admin-b@doc.example")
            session.flush()
            from app.modules.users.models import Role
            admin_a = session.get(User, admin_a.id)
            project = Project(
                tenant_id=tenant_a.id, name="API Heights", slug="api-heights", location="Pune",
                status=ProjectStatus.ACTIVE.value, created_by=admin_a.id,
            )
            session.add(project)
            session.flush()
            lead = Lead(
                tenant_id=tenant_a.id, full_name="API Buyer", email="api-buyer@doc.example",
                phone="+919800000003", project_id=project.id, source=LeadSource.WEBSITE.value,
                status=LeadStatus.CONVERTED.value, consent_to_contact=True,
            )
            session.add(lead)
            session.commit()
            installment, _receipt = _installment_and_receipt(session, admin_a, lead)
            installment_id = installment.id

        admin_headers = _login(client, "admin-a@doc.example")
        sales_headers = _login(client, "sales-a@doc.example")
        buyer_headers = _login(client, "buyer-a@doc.example")
        other_headers = _login(client, "admin-b@doc.example")

        issued = client.post(f"/api/v1/documents/demand-letters/{installment_id}", headers=admin_headers)
        assert issued.status_code == 201, issued.text
        document_id = issued.json()["id"]
        assert issued.json()["document_number"] == "DOC-DEMAND-000001"
        assert "storage_path" not in issued.json()
        assert client.post(f"/api/v1/documents/demand-letters/{installment_id}", headers=sales_headers).status_code == 403
        assert client.post(f"/api/v1/documents/demand-letters/{installment_id}", headers=buyer_headers).status_code == 403

        listing = client.get("/api/v1/documents?kind=DEMAND_LETTER", headers=sales_headers)
        assert listing.status_code == 200 and listing.json()["total"] == 1
        detail = client.get(f"/api/v1/documents/{document_id}", headers=sales_headers)
        assert detail.status_code == 200
        assert client.get(f"/api/v1/documents/{document_id}", headers=buyer_headers).status_code == 403
        assert client.get(f"/api/v1/documents/{document_id}", headers=other_headers).status_code == 404
        assert client.get(f"/api/v1/documents/{document_id}/download", headers=other_headers).status_code == 404

        download = client.get(f"/api/v1/documents/{document_id}/download", headers=sales_headers)
        assert download.status_code == 200
        assert download.headers["content-type"] == "application/pdf"
        assert "attachment" in download.headers["content-disposition"]
        assert "DOC-DEMAND-000001.pdf" in download.headers["content-disposition"]
        assert hashlib.sha256(download.content).hexdigest() == download.headers["x-document-sha256"]
        proof = client.get(f"/api/v1/documents/{document_id}/proof", headers=admin_headers)
        assert proof.status_code == 200
        assert proof.json()["content_sha256"] == download.headers["x-document-sha256"]
        assert proof.json()["payload_snapshot"]["bank_account_number"] == "XXXX3456"
        assert "1234567890123456" not in proof.text

        voided = client.post(f"/api/v1/documents/{document_id}/void", headers=admin_headers, json={"reason": "Corrected letter issued"})
        assert voided.status_code == 200 and voided.json()["status"] == "VOIDED"
        gone = client.get(f"/api/v1/documents/{document_id}/download", headers=admin_headers)
        assert gone.status_code == 410 and "Corrected letter issued" in gone.text
    finally:
        get_settings.cache_clear()


def test_storage_rejects_traversal_and_absolute_paths(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOCUMENTS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        for unsafe in ("../outside.pdf", "/absolute.pdf", "tenant/../../outside.pdf", "C:/outside.pdf", "tenant\\bad.pdf"):
            with pytest.raises(ValueError):
                storage.resolve_path(unsafe)
    finally:
        get_settings.cache_clear()
