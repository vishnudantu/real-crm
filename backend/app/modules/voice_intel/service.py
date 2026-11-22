"""Transcription job lifecycle + summary persistence.

Processing runs synchronously inside the request; a background worker is out of
scope. The provider is injectable so no real transcription/AI call is made in
tests. Completed transcripts are idempotent: reprocessing returns them unchanged.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.omnichannel.models import CallRecording
from app.modules.voice_intel.exceptions import (
    RecordingNotFoundError,
    SummaryNotFoundError,
    TranscriptNotFoundError,
)
from app.modules.voice_intel.models import CallSummary, CallTranscript, TranscriptStatus
from app.modules.voice_intel.providers import DeterministicFakeProvider, TranscriptionProvider

_default_provider = DeterministicFakeProvider()


def get_default_provider() -> TranscriptionProvider:
    return _default_provider


def get_transcript(
    session: Session, transcript_id: UUID, *, tenant_id: UUID
) -> CallTranscript | None:
    return session.scalar(
        select(CallTranscript).where(
            CallTranscript.id == transcript_id, CallTranscript.tenant_id == tenant_id
        )
    )


def require_transcript(
    session: Session, transcript_id: UUID, *, tenant_id: UUID
) -> CallTranscript:
    transcript = get_transcript(session, transcript_id, tenant_id=tenant_id)
    if transcript is None:
        raise TranscriptNotFoundError()
    return transcript


def list_transcripts(
    session: Session, *, tenant_id: UUID, status: str | None = None
) -> list[CallTranscript]:
    conditions = [CallTranscript.tenant_id == tenant_id]
    if status is not None:
        conditions.append(CallTranscript.status == status)
    return list(
        session.scalars(
            select(CallTranscript)
            .where(*conditions)
            .order_by(CallTranscript.created_at.desc(), CallTranscript.id)
        ).all()
    )


def get_summary(
    session: Session, transcript_id: UUID, *, tenant_id: UUID
) -> CallSummary:
    require_transcript(session, transcript_id, tenant_id=tenant_id)
    summary = session.scalar(
        select(CallSummary).where(
            CallSummary.transcript_id == transcript_id,
            CallSummary.tenant_id == tenant_id,
        )
    )
    if summary is None:
        raise SummaryNotFoundError()
    return summary


def enqueue_transcription(
    session: Session, *, tenant_id: UUID, call_recording_id: UUID, language: str = "en"
) -> CallTranscript:
    """Validate the recording belongs to the tenant and create a QUEUED transcript."""
    recording = session.scalar(
        select(CallRecording).where(
            CallRecording.id == call_recording_id,
            CallRecording.tenant_id == tenant_id,
        )
    )
    if recording is None:
        raise RecordingNotFoundError()
    transcript = CallTranscript(
        tenant_id=tenant_id,
        call_recording_id=recording.id,
        call_id=recording.call_id,
        language=language,
        status=TranscriptStatus.QUEUED.value,
    )
    session.add(transcript)
    session.flush()  # materialize id before commit/response
    session.commit()
    session.refresh(transcript)
    return transcript


def process_transcript(
    session: Session,
    transcript_id: UUID,
    *,
    tenant_id: UUID,
    provider: TranscriptionProvider | None = None,
) -> CallTranscript:
    """Run transcribe+summarize synchronously. Idempotent for COMPLETED rows."""
    transcript = require_transcript(session, transcript_id, tenant_id=tenant_id)
    if transcript.status == TranscriptStatus.COMPLETED.value:
        return transcript

    provider = provider or get_default_provider()
    recording = session.scalar(
        select(CallRecording).where(
            CallRecording.id == transcript.call_recording_id,
            CallRecording.tenant_id == tenant_id,
        )
    )
    if recording is None:
        raise RecordingNotFoundError()

    transcript.status = TranscriptStatus.PROCESSING.value
    transcript.error = None
    transcript.provider = provider.name
    session.add(transcript)
    session.flush()

    try:
        audio_ref = recording.storage_url or recording.egress_id or str(recording.id)
        result = provider.transcribe(audio_ref=audio_ref, language=transcript.language)
        text = result.get("text") or ""
        segments = result.get("segments") or []
        summary_payload = provider.summarize(transcript_text=text)
    except Exception as exc:  # noqa: BLE001 - provider failure becomes a FAILED row
        transcript.status = TranscriptStatus.FAILED.value
        transcript.error = str(exc)
        transcript.completed_at = None
        session.add(transcript)
        session.commit()
        session.refresh(transcript)
        return transcript

    transcript.transcript_text = text
    transcript.segments = segments
    transcript.status = TranscriptStatus.COMPLETED.value
    transcript.completed_at = datetime.now(UTC)
    session.add(transcript)
    session.flush()  # ensure transcript.id + state before summary insert

    existing = session.scalar(
        select(CallSummary).where(
            CallSummary.transcript_id == transcript.id,
            CallSummary.tenant_id == tenant_id,
        )
    )
    if existing is None:
        summary = CallSummary(
            tenant_id=tenant_id,
            transcript_id=transcript.id,
            summary=summary_payload.get("summary") or "",
            requirements=summary_payload.get("requirements") or {},
            objections=summary_payload.get("objections") or [],
            commitments=summary_payload.get("commitments") or [],
            next_actions=summary_payload.get("next_actions") or [],
        )
        session.add(summary)
    else:
        existing.summary = summary_payload.get("summary") or ""
        existing.requirements = summary_payload.get("requirements") or {}
        existing.objections = summary_payload.get("objections") or []
        existing.commitments = summary_payload.get("commitments") or []
        existing.next_actions = summary_payload.get("next_actions") or []
        session.add(existing)

    session.commit()
    session.refresh(transcript)
    return transcript
