"""voice_intel: call transcripts + AI call summaries

Revision ID: f8a9b0c1d2e3
Revises: b3c4d5e6f7a8
Create Date: 2026-11-22 22:00:00

Transcription/summary rows only — no raw audio is stored. Transcripts link to
omnichannel call_recordings (audio owner) and optionally call_records.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create voice intelligence tables.

    Composite tenant_id_id indexes are auto-emitted by app.db.tenancy's
    after_parent_attach listener; they are intentionally absent here.
    """
    op.create_table(
        "call_transcripts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("call_recording_id", sa.Uuid(), nullable=False),
        sa.Column("call_id", sa.Uuid(), nullable=True),
        sa.Column("language", sa.String(length=8), server_default="en", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="QUEUED", nullable=False),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("segments", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(length=64), server_default="deterministic-fake", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('QUEUED','PROCESSING','COMPLETED','FAILED')",
            name=op.f("ck_call_transcripts_status"),
        ),
        sa.ForeignKeyConstraint(["call_recording_id"], ["call_recordings.id"], name=op.f("fk_call_transcripts_call_recording_id_call_recordings"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["call_id"], ["call_records.id"], name=op.f("fk_call_transcripts_call_id_call_records"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_call_transcripts_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_call_transcripts")),
    )
    op.create_index(op.f("ix_call_transcripts_call_recording_id"), "call_transcripts", ["call_recording_id"], unique=False)
    op.create_index(op.f("ix_call_transcripts_call_id"), "call_transcripts", ["call_id"], unique=False)
    op.create_index(op.f("ix_call_transcripts_status"), "call_transcripts", ["status"], unique=False)
    op.create_index(op.f("ix_call_transcripts_tenant_id"), "call_transcripts", ["tenant_id"], unique=False)
    op.create_index("ix_call_transcripts_tenant_status", "call_transcripts", ["tenant_id", "status"], unique=False)

    op.create_table(
        "call_summaries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("transcript_id", sa.Uuid(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("objections", sa.JSON(), nullable=False),
        sa.Column("commitments", sa.JSON(), nullable=False),
        sa.Column("next_actions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["transcript_id"], ["call_transcripts.id"], name=op.f("fk_call_summaries_transcript_id_call_transcripts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_call_summaries_tenant_id_tenants"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_call_summaries")),
        sa.UniqueConstraint("tenant_id", "transcript_id", name="uq_call_summaries_tenant_transcript"),
    )
    op.create_index(op.f("ix_call_summaries_transcript_id"), "call_summaries", ["transcript_id"], unique=False)
    op.create_index(op.f("ix_call_summaries_tenant_id"), "call_summaries", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_call_summaries_tenant_id"), table_name="call_summaries")
    op.drop_index(op.f("ix_call_summaries_transcript_id"), table_name="call_summaries")
    op.drop_index("ix_call_summaries_tenant_id_id", table_name="call_summaries")
    op.drop_table("call_summaries")

    op.drop_index("ix_call_transcripts_tenant_status", table_name="call_transcripts")
    op.drop_index(op.f("ix_call_transcripts_tenant_id"), table_name="call_transcripts")
    op.drop_index(op.f("ix_call_transcripts_status"), table_name="call_transcripts")
    op.drop_index(op.f("ix_call_transcripts_call_id"), table_name="call_transcripts")
    op.drop_index(op.f("ix_call_transcripts_call_recording_id"), table_name="call_transcripts")
    op.drop_index("ix_call_transcripts_tenant_id_id", table_name="call_transcripts")
    op.drop_table("call_transcripts")
