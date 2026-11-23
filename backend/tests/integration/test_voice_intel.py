"""Integration tests for /voice-intel transcription + AI call summary."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.main import app
from app.modules.omnichannel.models import CallRecord, CallRecording
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName
from app.modules.voice_intel.models import CallSummary
from app.modules.voice_intel.providers import DeterministicFakeProvider
from app.modules.voice_intel.router import get_transcription_provider


@pytest.fixture()
def env(
    client: TestClient,
    override_db: None,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> dict:
    admin = user_factory(role=RoleName.ADMIN)
    headers = auth_headers(admin.email)
    with test_session_factory() as s:
        call = CallRecord(
            tenant_id=admin.tenant_id,
            agent_id=admin.id,
            direction="OUTBOUND",
            status="COMPLETED",
            provider="simulated",
            room_name=f"r-{uuid4().hex[:8]}",
        )
        s.add(call)
        s.flush()  # assign call.id before recording references it
        recording = CallRecording(
            tenant_id=admin.tenant_id,
            call_id=call.id,
            status="COMPLETED",
            storage_url="s3://test/audio.ogg",
            egress_id=f"egress-{uuid4().hex[:6]}",
        )
        s.add(recording)
        s.commit()
        return {
            "factory": test_session_factory,
            "tenant_id": admin.tenant_id,
            "admin_id": admin.id,
            "headers": headers,
            "call_id": call.id,
            "recording_id": recording.id,
        }


def _override_provider(provider) -> None:
    app.dependency_overrides[get_transcription_provider] = lambda: provider


def _clear_provider() -> None:
    app.dependency_overrides.pop(get_transcription_provider, None)


def _enqueue(client: TestClient, env: dict, **overrides) -> str:
    payload = {"call_recording_id": str(env["recording_id"]), "language": "en", **overrides}
    r = client.post("/api/v1/voice-intel/transcriptions", json=payload, headers=env["headers"])
    assert r.status_code == 201, r.text
    return r.json()["id"]


class TestEnqueue:
    def test_enqueue_creates_queued(self, client: TestClient, env: dict) -> None:
        r = client.post(
            "/api/v1/voice-intel/transcriptions",
            json={"call_recording_id": str(env["recording_id"]), "language": "en"},
            headers=env["headers"],
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == "QUEUED"
        assert body["call_recording_id"] == str(env["recording_id"])
        assert body["call_id"] == str(env["call_id"])
        assert body["language"] == "en"

    def test_enqueue_unknown_recording_404(self, client: TestClient, env: dict) -> None:
        r = client.post(
            "/api/v1/voice-intel/transcriptions",
            json={"call_recording_id": str(uuid4())},
            headers=env["headers"],
        )
        assert r.status_code == 404

    def test_enqueue_requires_admin(self, client: TestClient, env: dict, user_factory, auth_headers) -> None:
        sales = user_factory(role=RoleName.SALES_EXECUTIVE)
        headers = auth_headers(sales.email)
        r = client.post(
            "/api/v1/voice-intel/transcriptions",
            json={"call_recording_id": str(env["recording_id"])},
            headers=headers,
        )
        assert r.status_code == 403


class TestProcess:
    def test_process_completes_with_summary(self, client: TestClient, env: dict) -> None:
        _override_provider(DeterministicFakeProvider())
        try:
            tid = _enqueue(client, env)
            r = client.post(f"/api/v1/voice-intel/transcriptions/{tid}/process", headers=env["headers"])
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["status"] == "COMPLETED"
            assert body["transcript_text"]
            assert body["segments"]
            assert body["completed_at"] is not None

            rs = client.get(f"/api/v1/voice-intel/transcriptions/{tid}/summary", headers=env["headers"])
            assert rs.status_code == 200, rs.text
            summary = rs.json()
            assert summary["summary"]
            reqs = summary["requirements"]
            assert "budget" in reqs
            assert "configuration" in reqs
            assert summary["commitments"]
            assert any("needs_review" in c for c in summary["commitments"])
        finally:
            _clear_provider()

    def test_reprocess_completed_is_idempotent(self, client: TestClient, env: dict) -> None:
        _override_provider(DeterministicFakeProvider())
        try:
            tid = _enqueue(client, env)
            client.post(f"/api/v1/voice-intel/transcriptions/{tid}/process", headers=env["headers"])
            first = client.get(f"/api/v1/voice-intel/transcriptions/{tid}", headers=env["headers"]).json()
            again = client.post(f"/api/v1/voice-intel/transcriptions/{tid}/process", headers=env["headers"])
            assert again.status_code == 200
            assert again.json()["completed_at"] == first["completed_at"]
            assert again.json()["transcript_text"] == first["transcript_text"]
        finally:
            _clear_provider()

    def test_provider_failure_marks_failed(self, client: TestClient, env: dict) -> None:
        class _Boom(DeterministicFakeProvider):
            name = "boom"

            def transcribe(self, *, audio_ref, language):
                raise RuntimeError("provider outage")

        _override_provider(_Boom())
        try:
            tid = _enqueue(client, env)
            r = client.post(f"/api/v1/voice-intel/transcriptions/{tid}/process", headers=env["headers"])
            assert r.status_code == 200
            body = r.json()
            assert body["status"] == "FAILED"
            assert "provider outage" in (body["error"] or "")
            assert body["completed_at"] is None
        finally:
            _clear_provider()


class TestIsolation:
    def test_cross_tenant_transcript_404(
        self, client: TestClient, env: dict, user_factory, auth_headers
    ) -> None:
        _override_provider(DeterministicFakeProvider())
        try:
            tid = _enqueue(client, env)
            client.post(f"/api/v1/voice-intel/transcriptions/{tid}/process", headers=env["headers"])
            other = Tenant(slug=f"o-{uuid4().hex[:8]}", name="O")
            with env["factory"]() as s:
                s.add(other)
                s.commit()
            other_admin = user_factory(role=RoleName.ADMIN, tenant=other)
            other_headers = auth_headers(other_admin.email)
            r = client.get(f"/api/v1/voice-intel/transcriptions/{tid}", headers=other_headers)
            assert r.status_code == 404
            rs = client.get(f"/api/v1/voice-intel/transcriptions/{tid}/summary", headers=other_headers)
            assert rs.status_code == 404
        finally:
            _clear_provider()

    def test_list_is_tenant_scoped(self, client: TestClient, env: dict) -> None:
        tid = _enqueue(client, env)
        r = client.get("/api/v1/voice-intel/transcriptions", headers=env["headers"])
        assert r.status_code == 200
        ids = {i["id"] for i in r.json()["items"]}
        assert tid in ids


class TestSummary:
    def test_one_summary_per_transcript(self, client: TestClient, env: dict) -> None:
        _override_provider(DeterministicFakeProvider())
        try:
            tid = _enqueue(client, env)
            client.post(f"/api/v1/voice-intel/transcriptions/{tid}/process", headers=env["headers"])
            client.post(f"/api/v1/voice-intel/transcriptions/{tid}/process", headers=env["headers"])
            with env["factory"]() as s:
                rows = s.query(CallSummary).filter_by(transcript_id=UUID(tid)).all()
                assert len(rows) == 1
        finally:
            _clear_provider()

    def test_summary_missing_before_processing(self, client: TestClient, env: dict) -> None:
        tid = _enqueue(client, env)
        r = client.get(f"/api/v1/voice-intel/transcriptions/{tid}/summary", headers=env["headers"])
        assert r.status_code == 404


class TestReadRoles:
    def test_sales_exec_can_read(self, client: TestClient, env: dict, user_factory, auth_headers) -> None:
        _override_provider(DeterministicFakeProvider())
        try:
            tid = _enqueue(client, env)
            client.post(f"/api/v1/voice-intel/transcriptions/{tid}/process", headers=env["headers"])
            sales = user_factory(role=RoleName.SALES_EXECUTIVE)
            headers = auth_headers(sales.email)
            r = client.get(f"/api/v1/voice-intel/transcriptions/{tid}", headers=headers)
            assert r.status_code == 200
            rs = client.get(f"/api/v1/voice-intel/transcriptions/{tid}/summary", headers=headers)
            assert rs.status_code == 200
        finally:
            _clear_provider()

    def test_buyer_cannot_read(self, client: TestClient, env: dict, user_factory, auth_headers) -> None:
        tid = _enqueue(client, env)
        buyer = user_factory(role=RoleName.BUYER)
        headers = auth_headers(buyer.email)
        r = client.get(f"/api/v1/voice-intel/transcriptions/{tid}", headers=headers)
        assert r.status_code == 403
