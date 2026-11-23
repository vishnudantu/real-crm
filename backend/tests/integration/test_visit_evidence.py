"""Staff site-visit evidence: upload, list, review, download, RBAC, isolation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.modules.auth.security import hash_password
from app.modules.bookings import service
from app.modules.bookings import evidence_storage
from app.modules.bookings.models import Booking, BookingStatus, EvidenceStatus, VisitSlot
from app.modules.bookings.schemas import BookingCreateRequest
from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD

PNG_BYTES = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c6360000002000154a24f5d0000000049454e44ae426082")


def _fixture(session: Session):
    tenant = Tenant(slug=f"ev-{uuid4().hex[:8]}", name="Evidence Co")
    session.add(tenant)
    session.flush()
    role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one_or_none()
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    admin = User(
        tenant_id=tenant.id, full_name="Admin", email=f"a.{tenant.id.hex[:8]}@ev.example",
        password_hash=hash_password(TEST_PASSWORD), role_id=role.id, is_active=True,
    )
    session.add(admin)
    session.flush()
    session.refresh(admin)
    project = Project(
        tenant_id=tenant.id, name="Towers", slug=f"towers-{tenant.id.hex[:8]}", location="Pune",
        status=ProjectStatus.ACTIVE.value, created_by=admin.id,
    )
    session.add(project)
    session.flush()
    lead = Lead(
        tenant_id=tenant.id, full_name="Buyer One", email=f"b.{tenant.id.hex[:8]}@ev.example",
        phone="+919800000012", project_id=project.id, source=LeadSource.WEBSITE.value,
        status=LeadStatus.VISIT_BOOKED.value, consent_to_contact=True,
    )
    session.add(lead)
    session.flush()
    slot = VisitSlot(
        tenant_id=tenant.id, project_id=project.id,
        start_time=datetime.now(UTC) + timedelta(days=1),
        end_time=datetime.now(UTC) + timedelta(days=1, hours=1),
        capacity=5, is_active=True,
    )
    session.add(slot)
    session.commit()
    return tenant, admin, project, lead, slot


def _booking(session: Session, admin: User, lead: Lead, slot: VisitSlot) -> Booking:
    booking = service.create_booking(
        session, actor=admin,
        payload=BookingCreateRequest(slot_id=slot.id, lead_id=lead.id),
    )
    # create_booking returns BookingResponse; fetch the ORM row for id.
    from app.modules.bookings import repository
    return repository.get_booking_by_id(session, booking.id, tenant_id=admin.tenant_id)


def test_upload_list_review_download_evidence(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("VISIT_EVIDENCE_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with test_session_factory() as session:
            tenant, admin, _p, lead, slot = _fixture(session)
            booking = _booking(session, admin, lead, slot)
            evidence = service.upload_visit_evidence(
                session, actor=admin, booking_id=booking.id,
                contents=PNG_BYTES, content_type="image/png", notes="Site photo",
            )
            assert evidence.status == EvidenceStatus.SUBMITTED.value
            assert evidence.size_bytes == len(PNG_BYTES)
            assert len(evidence.content_sha256) == 64

            # One file on disk under the tenant subfolder.
            files = list(tmp_path.rglob("*"))
            assert any(f.is_file() for f in files)

            rows = service.list_visit_evidence(session, actor=admin, booking_id=booking.id)
            assert len(rows) == 1 and rows[0].id == evidence.id

            reviewed = service.review_visit_evidence(
                session, actor=admin, evidence_id=evidence.id, decision="VERIFIED", review_note="Looks good"
            )
            assert reviewed.status == EvidenceStatus.VERIFIED.value
            assert reviewed.verified_by_id == admin.id

            ev, path = service.get_evidence_for_download(session, actor=admin, evidence_id=evidence.id)
            assert path.read_bytes() == PNG_BYTES

            # Only SUBMITTED can be reviewed.
            import pytest as _pytest
            from fastapi import HTTPException
            with _pytest.raises(HTTPException):
                service.review_visit_evidence(
                    session, actor=admin, evidence_id=evidence.id, decision="REJECTED"
                )
    finally:
        get_settings.cache_clear()


def test_evidence_rejects_bad_type_and_empty(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("VISIT_EVIDENCE_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        from fastapi import HTTPException
        with test_session_factory() as session:
            _t, admin, _p, lead, slot = _fixture(session)
            booking = _booking(session, admin, lead, slot)
            with pytest.raises(HTTPException):
                service.upload_visit_evidence(
                    session, actor=admin, booking_id=booking.id,
                    contents=PNG_BYTES, content_type="text/html",
                )
            with pytest.raises(HTTPException):
                service.upload_visit_evidence(
                    session, actor=admin, booking_id=booking.id,
                    contents=b"", content_type="image/png",
                )
    finally:
        get_settings.cache_clear()


def test_storage_failure_leaves_no_row(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("VISIT_EVIDENCE_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with test_session_factory() as session:
            _t, admin, _p, lead, slot = _fixture(session)
            booking = _booking(session, admin, lead, slot)

            def fail(**_kwargs):
                raise OSError("disk full")

            monkeypatch.setattr(evidence_storage, "write_evidence", fail)
            with pytest.raises(OSError):
                service.upload_visit_evidence(
                    session, actor=admin, booking_id=booking.id,
                    contents=PNG_BYTES, content_type="image/png",
                )
            assert service.list_visit_evidence(session, actor=admin, booking_id=booking.id) == []
    finally:
        get_settings.cache_clear()


def test_buyer_cannot_upload_evidence(
    test_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("VISIT_EVIDENCE_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        with test_session_factory() as session:
            _t, admin, _p, lead, slot = _fixture(session)
            booking = _booking(session, admin, lead, slot)
            from app.modules.users.exceptions import InsufficientPermissionsError
            from types import SimpleNamespace
            # Detached buyer actor avoids mutating ORM relationships in the test.
            buyer_actor = SimpleNamespace(
                id=uuid4(), tenant_id=admin.tenant_id,
                role=SimpleNamespace(name=RoleName.BUYER.value),
            )
            with pytest.raises(InsufficientPermissionsError):
                service.upload_visit_evidence(
                    session, actor=buyer_actor, booking_id=booking.id,
                    contents=PNG_BYTES, content_type="image/png",
                )
    finally:
        get_settings.cache_clear()


def test_evidence_api_upload_and_list(
    client, override_db, seeded_roles, test_session_factory, user_factory, auth_headers,
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    monkeypatch.setenv("VISIT_EVIDENCE_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        admin = user_factory(role=RoleName.ADMIN)
        headers = auth_headers(admin.email)
        with test_session_factory() as session:
            admin = session.get(User, admin.id)
            tenant = session.get(Tenant, admin.tenant_id)
            project = Project(
                tenant_id=tenant.id, name="API Towers", slug=f"apit-{tenant.id.hex[:6]}", location="Pune",
                status=ProjectStatus.ACTIVE.value, created_by=admin.id,
            )
            session.add(project)
            session.flush()
            lead = Lead(
                tenant_id=tenant.id, full_name="Buyer", email=f"apib.{tenant.id.hex[:6]}@ev.example",
                phone="+919800000013", project_id=project.id, source=LeadSource.WEBSITE.value,
                status=LeadStatus.VISIT_BOOKED.value, consent_to_contact=True,
            )
            session.add(lead)
            session.flush()
            slot = VisitSlot(
                tenant_id=tenant.id, project_id=project.id,
                start_time=datetime.now(UTC) + timedelta(days=1),
                end_time=datetime.now(UTC) + timedelta(days=1, hours=1),
                capacity=5, is_active=True,
            )
            session.add(slot)
            session.commit()
            booking = _booking(session, admin, lead, slot)
            booking_id = booking.id

        r = client.post(
            f"/api/v1/bookings/{booking_id}/evidence?notes=From%20mobile",
            headers={**headers, "content-type": "image/png"},
            content=PNG_BYTES,
        )
        assert r.status_code == 201, r.text
        evidence_id = r.json()["id"]
        assert r.json()["status"] == "SUBMITTED"

        listed = client.get(f"/api/v1/bookings/{booking_id}/evidence", headers=headers)
        assert listed.status_code == 200 and len(listed.json()) == 1

        reviewed = client.post(
            f"/api/v1/bookings/evidence/{evidence_id}/review",
            headers=headers, json={"decision": "VERIFIED", "review_note": "ok"},
        )
        assert reviewed.status_code == 200 and reviewed.json()["status"] == "VERIFIED"

        dl = client.get(f"/api/v1/bookings/evidence/{evidence_id}/download", headers=headers)
        assert dl.status_code == 200
        assert dl.content == PNG_BYTES
        assert dl.headers["x-content-sha256"] == r.json()["content_sha256"]
    finally:
        get_settings.cache_clear()
