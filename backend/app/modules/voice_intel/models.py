"""Tenant-owned call transcripts and AI-generated call summaries.

No raw audio is persisted here: transcripts link to an existing omnichannel
``call_recordings`` row (which owns the audio artifact) and store only the
derived text, segments, and structured summary.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.tenancy import TenantOwned


def utcnow() -> datetime:
    return datetime.now(UTC)


def _quoted(values: type[StrEnum]) -> str:
    return ", ".join(f"'{v.value}'" for v in values)


class TranscriptStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CallTranscript(TenantOwned, Base):
    """A transcription job + its derived text for one call recording."""

    __tablename__ = "call_transcripts"
    __table_args__ = (
        CheckConstraint(
            f"status IN ({_quoted(TranscriptStatus)})", name="ck_call_transcripts_status"
        ),
        Index("ix_call_transcripts_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    call_recording_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("call_recordings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    call_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("call_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TranscriptStatus.QUEUED.value, index=True
    )
    transcript_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    segments: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="deterministic-fake")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(), onupdate=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    summary: Mapped["CallSummary | None"] = relationship(
        back_populates="transcript", cascade="all, delete-orphan", uselist=False
    )


class CallSummary(TenantOwned, Base):
    """Structured AI summary of a completed call transcript (one per transcript)."""

    __tablename__ = "call_summaries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "transcript_id", name="uq_call_summaries_tenant_transcript"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    transcript_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("call_transcripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    objections: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    commitments: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    next_actions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(), onupdate=utcnow
    )

    transcript: Mapped[CallTranscript] = relationship(back_populates="summary")
