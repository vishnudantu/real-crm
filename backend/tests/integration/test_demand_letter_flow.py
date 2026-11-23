"""P0.3 demand-letter approval gate and outbound delivery tracking.

Covers the full review -> send lifecycle: prepare creates a PENDING_REVIEW
document plus a PENDING DEMAND_LETTER approval with no sent timestamp; an
admin approval releases the letter (sent_at stamped, outbox row queued); a
rejection voids the letter without any outbox event; the delivery endpoint
surfaces the queued-then-sent state; the legacy postsales send routes through
the gate; and cross-tenant access stays 404.

A no-op log provider is used everywhere so no real send happens in tests.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.modules.approvals.models import ApprovalRequest, ApprovalStatus
from app.modules.documents import service as document_service
from app.modules.documents.models import Document, DocumentReviewState, DocumentStatus
from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.messaging.dispatcher import process_due_deliveries
from app.modules.messaging.models import DeliveryStatus, MessageDelivery
from app.modules.messaging.providers.log_provider import LogProvider
from app.modules.postsales import service as postsales_service
from app.modules.postsales.models import Installment
from app.modules.postsales.schemas import (
    InstallmentSpec,
    PaymentPlanCreateRequest,
    PaymentPlanType,
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


def _fixture(session: Session, *, slug_prefix: str = "dl") -> tuple[Tenant, User, Project, Lead]:
    tenant = Tenant(
        slug=f"{slug_prefix}-{uuid4().hex[:8]}", name="Demand Letter Realty",
        theme_json={
            "legal_entity_name": "Demand Letter Realty Private Limited",
            "bank": {"name": "Example Bank", "account_name": "DL Realty",
                     "account_number": "1234567890123456", "ifsc": "EXAM0001234"},
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
        tenant_id=tenant.id, full_name="Gate Admin",
        email=f"admin.{tenant.id.hex[:8]}@example.test",
        password_hash="test-not-a-password", role_id=role.id, is_active=True,
    )
    session.add(admin)
    session.flush()
    project = Project(
        tenant_id=tenant.id, name="Gate Heights", slug=f"gate-{tenant.id.hex[:8]}",
        location="Pune", status=ProjectStatus.ACTIVE.value, created_by=admin.id,
        rera_number="P52100000000",
    )
    session.add(project)
    session.flush()
    lead = Lead(
        tenant_id=tenant.id, full_name="Buyer One",
        email=f"buyer.{tenant.id.hex[:8]}@example.test",
        phone="+919800000001", project_id=project.id, source=LeadSource.WEBSITE.value,
        status=LeadStatus.CONVERTED.value, consent_to_contact=True,
    )
    session.add(lead)
    session.commit()
    return tenant, admin, project, lead


def _installment(session: Session, admin: User, lead: Lead) -> Installment:
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
    return plan.installments[0]


def _seed_outbox_rule(session: Session, tenant_id) -> None:
    """A live trigger rule so the released event actually queues a delivery."""
    from app.modules.messaging.models import MessageTemplate, TriggerRule

    template = MessageTemplate(
        tenant_id=tenant_id, name="Demand letter issued", channel="EMAIL",
        language="en", body="Dear {customer_name}, demand {document_number} for "
        "{unit_code} ({amount}) is ready.", is_active=True,
    )
    session.add(template)
    session.flush()
    session.add(TriggerRule(
        tenant_id=tenant_id, event="document.demand_letter_issued", channel="EMAIL",
        template_id=template.id, enabled=True, delay_minutes=0,
    ))
    session.commit()


def _queued_deliveries(session: Session, document_id) -> list[MessageDelivery]:
    return list(
        session.query(MessageDelivery)
        .filter(MessageDelivery.entity_id == document_id)
        .all()
    )


# --------------------------------------------------------------------------- #
# Service-level lifecycle


def test_prepare_creates_pending_document_and_approval_without_send_marker(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("DOCUMENTS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with test_session_factory() as session:
            _tenant, admin, _project, lead = _fixture(session)
            installment = _installment(session, admin, lead)

            document, approval = document_service.prepare_demand_letter(
                session, actor=admin, installment_id=installment.id
            )
            assert document.status == DocumentStatus.ISSUED.value
            assert document.review_state == DocumentReviewState.PENDING_REVIEW.value
            assert approval is not None
            assert approval.status == ApprovalStatus.PENDING.value
            assert approval.request_type == "DEMAND_LETTER"
            assert approval.reference_type == "document"
            assert approval.reference_id == document.id

            session.refresh(installment)
            assert installment.demand_letter_sent_at is None
            assert installment.status != "DUE" or installment.due_on <= date.today()
            assert _queued_deliveries(session, document.id) == []
    finally:
        get_settings.cache_clear()


def test_admin_approval_releases_letter_and_queues_outbox_delivery(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("DOCUMENTS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with test_session_factory() as session:
            tenant, admin, _project, lead = _fixture(session)
            _seed_outbox_rule(session, tenant.id)
            installment = _installment(session, admin, lead)

            from app.modules.users.models import Role

            sales_role = session.query(Role).filter_by(
                name=RoleName.SALES_EXECUTIVE.value
            ).one_or_none() or Role(name=RoleName.SALES_EXECUTIVE.value)
            if sales_role.id is None:
                session.add(sales_role)
                session.flush()
            from app.modules.auth.security import hash_password
            sales = User(
                tenant_id=tenant.id, full_name="Prep Exec",
                email=f"sales.{tenant.id.hex[:8]}@example.test",
                password_hash=hash_password(TEST_PASSWORD), role_id=sales_role.id,
                is_active=True,
            )
            session.add(sales)
            session.commit()

            document, approval = document_service.prepare_demand_letter(
                session, actor=sales, installment_id=installment.id
            )
            session.refresh(installment)
            assert installment.demand_letter_sent_at is None

            released = document_service.release_demand_letter(
                session, actor=admin, document_id=document.id
            )
            assert released.review_state == DocumentReviewState.APPROVED_FOR_SEND.value
            assert released.approved_by == admin.id
            assert released.approved_at is not None

            session.refresh(installment)
            assert installment.demand_letter_sent_at is not None
            assert installment.status == "DUE"

            queued = _queued_deliveries(session, document.id)
            assert len(queued) == 1
            assert queued[0].status == DeliveryStatus.QUEUED.value
            assert queued[0].event == "document.demand_letter_issued"
            assert str(document.id) in queued[0].idempotency_key

            # Idempotent release does not double-queue.
            again = document_service.release_demand_letter(
                session, actor=admin, document_id=document.id
            )
            assert again.id == document.id
            assert len(_queued_deliveries(session, document.id)) == 1
    finally:
        get_settings.cache_clear()


def test_rejection_voids_document_and_queues_no_outbox_event(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("DOCUMENTS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with test_session_factory() as session:
            _tenant, admin, _project, lead = _fixture(session)
            _seed_outbox_rule(session, _tenant.id)
            installment = _installment(session, admin, lead)

            document, approval = document_service.prepare_demand_letter(
                session, actor=admin, installment_id=installment.id
            )
            rejected = document_service.reject_demand_letter(
                session, actor=admin, document_id=document.id, reason="Wrong amount"
            )
            assert rejected.status == DocumentStatus.VOIDED.value
            assert rejected.void_reason == "Wrong amount"
            assert rejected.review_state == DocumentReviewState.VOIDED.value
            # The service-level reject helper only touches the document; the
            # approval decision (which syncs it) flows through decide().
            session.refresh(approval)
            assert approval.status == ApprovalStatus.PENDING.value

            session.refresh(installment)
            assert installment.demand_letter_sent_at is None
            assert _queued_deliveries(session, document.id) == []

            with pytest.raises(Exception) as blocked:
                document_service.release_demand_letter(
                    session, actor=admin, document_id=document.id
                )
            assert getattr(blocked.value, "status_code", None) == 409
    finally:
        get_settings.cache_clear()


def test_delivery_state_tracks_queued_then_sent(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("DOCUMENTS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with test_session_factory() as session:
            tenant, admin, _project, lead = _fixture(session)
            _seed_outbox_rule(session, tenant.id)
            installment = _installment(session, admin, lead)

            document, _approval = document_service.prepare_demand_letter(
                session, actor=admin, installment_id=installment.id
            )

            state = document_service.delivery_state_for_document(session, document)
            assert state["delivery_state"] == DocumentReviewState.PENDING_REVIEW.value
            assert state["delivery_status"] is None

            document_service.release_demand_letter(
                session, actor=admin, document_id=document.id
            )
            state = document_service.delivery_state_for_document(session, document)
            assert state["delivery_state"] == DeliveryStatus.QUEUED.value
            assert state["delivery_status"] == DeliveryStatus.QUEUED.value

            session.commit()

        # No-op provider: the dispatcher accepts the row without any real send.
        provider = LogProvider()
        with test_session_factory() as session:
            counts = process_due_deliveries(
                session, provider_factory=lambda name, settings: provider
            )
            assert counts["sent"] == 1

        with test_session_factory() as session:
            reloaded = session.get(Document, document.id)
            state = document_service.delivery_state_for_document(session, reloaded)
            assert state["delivery_state"] == DeliveryStatus.SENT.value
            assert state["delivery_status"] == DeliveryStatus.SENT.value
            assert state["sent_at"] is not None
            assert state["latest_delivery_error"] is None
            assert state["attempts"] == 1
    finally:
        get_settings.cache_clear()


# --------------------------------------------------------------------------- #
# Back-compat: legacy postsales send routes through the gate


def test_send_demand_letter_prepares_and_requires_second_admin_approval(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("DOCUMENTS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with test_session_factory() as session:
            tenant, admin, _project, lead = _fixture(session)
            _seed_outbox_rule(session, tenant.id)
            installment = _installment(session, admin, lead)

            # The requesting admin cannot approve their own request.
            with pytest.raises(Exception) as forbidden:
                postsales_service.send_demand_letter(
                    session, actor=admin, installment_id=installment.id
                )
                from app.modules.approvals import service as approvals_service
                approvals_service.decide(
                    session, actor=admin,
                    request_id=session.query(ApprovalRequest).one().id,
                    decision="APPROVED",
                )
            assert getattr(forbidden.value, "status_code", None) == 409  # SelfApprovalError

            session.rollback()
            result = postsales_service.send_demand_letter(
                session, actor=admin, installment_id=installment.id
            )
            document = result.__dict__["demand_letter_document"]
            assert document.review_state == DocumentReviewState.PENDING_REVIEW.value
            session.refresh(installment)
            assert installment.demand_letter_sent_at is None
            approval = session.query(ApprovalRequest).filter_by(
                reference_id=document.id, request_type="DEMAND_LETTER"
            ).one()
            assert approval.status == ApprovalStatus.PENDING.value
            assert approval.requested_by_id == admin.id
            assert _queued_deliveries(session, document.id) == []

            # A different admin decides; release happens automatically.
            from app.modules.auth.security import hash_password
            from app.modules.users.models import Role
            second_role = session.query(Role).filter_by(
                name=RoleName.ADMIN.value
            ).one_or_none()
            assert second_role is not None
            second_admin = User(
                tenant_id=tenant.id, full_name="Second Admin",
                email=f"admin2.{tenant.id.hex[:8]}@example.test",
                password_hash=hash_password(TEST_PASSWORD), role_id=second_role.id,
                is_active=True,
            )
            session.add(second_admin)
            session.commit()
            decided = approvals_service.decide(
                session, actor=second_admin, request_id=approval.id, decision="APPROVED"
            )
            assert decided.status == ApprovalStatus.APPROVED.value

            session.expire_all()
            released = session.get(Document, document.id)
            assert released.review_state == DocumentReviewState.APPROVED_FOR_SEND.value
            assert len(_queued_deliveries(session, document.id)) == 1
            refreshed_installment = session.get(Installment, installment.id)
            assert refreshed_installment.demand_letter_sent_at is not None
    finally:
        get_settings.cache_clear()


def test_send_demand_letter_after_direct_issue_releases_immediately(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Established issue-then-send sequences keep working back-compat."""

    monkeypatch.setenv("DOCUMENTS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with test_session_factory() as session:
            tenant, admin, _project, lead = _fixture(session)
            _seed_outbox_rule(session, tenant.id)
            installment = _installment(session, admin, lead)

            issued = document_service.issue_demand_letter(
                session, actor=admin, installment_id=installment.id
            )
            assert issued.review_state == DocumentReviewState.APPROVED.value

            result = postsales_service.send_demand_letter(
                session, actor=admin, installment_id=installment.id
            )
            assert result.__dict__["demand_letter_document"].id == issued.id
            assert result.demand_letter_sent_at is not None
            assert result.status == "DUE"
            assert len(_queued_deliveries(session, issued.id)) == 1
    finally:
        get_settings.cache_clear()


# --------------------------------------------------------------------------- #
# API surface


@pytest.fixture()
def api_env(
    client: TestClient,
    override_db: None,
    seeded_roles: None,
    test_session_factory: sessionmaker[Session],
    user_factory: Callable[..., User],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> dict:
    monkeypatch.setenv("DOCUMENTS_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    with test_session_factory() as session:
        tenant, _admin, _project, lead = _fixture(session, slug_prefix="dlapi")
        _seed_outbox_rule(session, tenant.id)
        installment = _installment(session, _admin, lead)
        other_tenant = Tenant(slug=f"dlapi-other-{uuid4().hex[:8]}", name="Other Tenant")
        session.add(other_tenant)
        session.commit()
        session.refresh(other_tenant)
    admin = user_factory(role=RoleName.ADMIN, tenant=tenant)
    sales = user_factory(role=RoleName.SALES_EXECUTIVE, tenant=tenant)
    other_admin = user_factory(role=RoleName.ADMIN, tenant=other_tenant)
    return {
        "factory": test_session_factory,
        "installment_id": installment.id,
        "admin_headers": _login(client, admin.email),
        "sales_headers": _login(client, sales.email),
        "other_headers": _login(client, other_admin.email),
    }


def test_api_prepare_gate_decision_and_delivery_tracking(api_env: dict, client: TestClient) -> None:
    prepared = client.post(
        f"/api/v1/documents/demand-letters/{api_env['installment_id']}/prepare",
        headers=api_env["sales_headers"],
    )
    assert prepared.status_code == 201, prepared.text
    body = prepared.json()
    document_id = body["id"]
    assert body["review_state"] == DocumentReviewState.PENDING_REVIEW.value
    approval_id = body["pending_approval_id"]
    assert approval_id is not None

    delivery = client.get(f"/api/v1/documents/{document_id}/delivery", headers=api_env["sales_headers"])
    assert delivery.status_code == 200
    assert delivery.json()["delivery_state"] == DocumentReviewState.PENDING_REVIEW.value

    # Sales staff cannot decide; the admin approves through the existing endpoint.
    denied = client.post(
        f"/api/v1/approvals/requests/{approval_id}/decision",
        json={"decision": "APPROVED"}, headers=api_env["sales_headers"],
    )
    assert denied.status_code == 403
    decided = client.post(
        f"/api/v1/approvals/requests/{approval_id}/decision",
        json={"decision": "APPROVED", "note": "Amounts verified against the plan."},
        headers=api_env["admin_headers"],
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == ApprovalStatus.APPROVED.value

    delivery = client.get(f"/api/v1/documents/{document_id}/delivery", headers=api_env["sales_headers"])
    assert delivery.status_code == 200
    assert delivery.json()["delivery_state"] == DeliveryStatus.QUEUED.value
    assert delivery.json()["review_state"] == DocumentReviewState.APPROVED_FOR_SEND.value

    with api_env["factory"]() as session:
        counts = process_due_deliveries(
            session, provider_factory=lambda name, settings: LogProvider()
        )
        assert counts["sent"] == 1

    delivery = client.get(f"/api/v1/documents/{document_id}/delivery", headers=api_env["sales_headers"])
    assert delivery.json()["delivery_state"] == DeliveryStatus.SENT.value
    assert delivery.json()["delivery_status"] == DeliveryStatus.SENT.value
    assert delivery.json()["sent_at"] is not None


def test_api_reject_voids_letter_and_cross_tenant_access_is_404(api_env: dict, client: TestClient) -> None:
    prepared = client.post(
        f"/api/v1/documents/demand-letters/{api_env['installment_id']}/prepare",
        headers=api_env["sales_headers"],
    )
    assert prepared.status_code == 201, prepared.text
    document_id = prepared.json()["id"]
    approval_id = prepared.json()["pending_approval_id"]

    rejected = client.post(
        f"/api/v1/approvals/requests/{approval_id}/decision",
        json={"decision": "REJECTED", "note": "Wrong installment selected."},
        headers=api_env["admin_headers"],
    )
    assert rejected.status_code == 200, rejected.text
    detail = client.get(f"/api/v1/documents/{document_id}", headers=api_env["admin_headers"])
    assert detail.json()["status"] == DocumentStatus.VOIDED.value
    assert detail.json()["review_state"] == DocumentReviewState.VOIDED.value

    delivery = client.get(f"/api/v1/documents/{document_id}/delivery", headers=api_env["admin_headers"])
    assert delivery.json()["delivery_state"] == DocumentReviewState.VOIDED.value
    with api_env["factory"]() as session:
        assert session.query(MessageDelivery).filter(
            MessageDelivery.entity_id == UUID(document_id)
        ).count() == 0

    assert client.get(f"/api/v1/documents/{document_id}/delivery", headers=api_env["other_headers"]).status_code == 404
    assert client.post(
        f"/api/v1/documents/demand-letters/{api_env['installment_id']}/prepare",
        headers=api_env["other_headers"],
    ).status_code == 404
    assert client.get(f"/api/v1/documents/{document_id}/delivery", headers=api_env["sales_headers"]).status_code == 200


def test_api_prepare_requires_staff_role(api_env: dict, client: TestClient, user_factory, auth_headers) -> None:
    buyer = user_factory(role=RoleName.BUYER, tenant=None)
    response = client.post(
        f"/api/v1/documents/demand-letters/{api_env['installment_id']}/prepare",
        headers=auth_headers(buyer.email),
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------- #
# Migration evidence (isolated in-memory SQLite; the real DB is never touched)


def test_migration_upgrade_and_downgrade_on_isolated_sqlite() -> None:
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    import sqlalchemy as sa
    from sqlalchemy.pool import StaticPool

    migration_path = next(
        (Path(__file__).parents[2] / "alembic" / "versions").glob("*e9a0b1c2d3e4*")
    )
    spec = importlib.util.spec_from_file_location("demand_letter_gate_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "e9a0b1c2d3e4"
    assert migration.down_revision == "e7f8a9b0c1d2"

    engine = sa.create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    try:
        metadata = sa.MetaData()
        sa.Table("tenants", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
        sa.Table("users", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
        documents = sa.Table(
            "documents", metadata,
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column("kind", sa.String(32), nullable=False),
            sa.Column("reference_type", sa.String(24), nullable=False),
            sa.Column("reference_id", sa.Uuid(), nullable=False),
            sa.Column("template_version", sa.Integer(), nullable=False),
            sa.Column("document_number", sa.String(64), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
            sa.Column("storage_path", sa.String(500), nullable=False),
            sa.Column("content_sha256", sa.String(64), nullable=False),
            sa.Column("payload_snapshot", sa.JSON(), nullable=False),
            sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        metadata.create_all(engine)
        tenant_id, user_id, document_id = uuid4(), uuid4(), uuid4()
        with engine.begin() as connection:
            connection.execute(
                sa.insert(documents).values(
                    id=document_id, tenant_id=tenant_id, kind="DEMAND_LETTER",
                    reference_type="installment", reference_id=uuid4(),
                    template_version=1, document_number="DOC-DEMAND-000001",
                    status="ISSUED", storage_path="t/d.pdf", content_sha256="a" * 64,
                    payload_snapshot={},
                    created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
                )
            )

        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            migration.op = Operations(context)
            migration.upgrade()
            inspector = sa.inspect(connection)
            columns = {col["name"] for col in inspector.get_columns("documents")}
            assert {"review_state", "approved_by", "approved_at"} <= columns
            assert "ix_documents_tenant_review_state" in {
                index["name"] for index in inspector.get_indexes("documents")
            }

            # Pre-existing rows must read as already-approved.
            review_state = connection.execute(
                sa.text("SELECT review_state FROM documents WHERE id = :id"),
                {"id": document_id.hex},
            ).scalar_one()
            assert review_state == "APPROVED"

            migration.downgrade()
            inspector = sa.inspect(connection)
            columns = {col["name"] for col in inspector.get_columns("documents")}
            assert not {"review_state", "approved_by", "approved_at"} & columns
    finally:
        engine.dispose()
