"""Versioned document templates and immutable issued document metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.tenancy import TenantOwned


class DocumentTemplateKey(StrEnum):
    DEMAND_LETTER = "DEMAND_LETTER"
    RECEIPT = "RECEIPT"
    STATEMENT = "STATEMENT"


class DocumentStatus(StrEnum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    VOIDED = "VOIDED"


class DocumentReviewState(StrEnum):
    """Delivery-gate lifecycle for an issued document (P0.3).

    ``APPROVED`` is the server default so every pre-existing document keeps
    behaving as already-approved; only the prepare flow writes the pending
    state and only an admin approval releases it for send.
    """

    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED_FOR_SEND = "APPROVED_FOR_SEND"
    APPROVED = "APPROVED"
    VOIDED = "VOIDED"


def utcnow() -> datetime:
    return datetime.now(UTC)


class DocumentTemplate(TenantOwned, Base):
    """A tenant-owned, immutable-version template using messaging merge tags."""

    __tablename__ = "document_templates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "key", "version", name="uq_document_templates_tenant_key_version"
        ),
        CheckConstraint(
            "key IN ('DEMAND_LETTER','RECEIPT','STATEMENT')",
            name="document_template_key_valid",
        ),
        CheckConstraint("version > 0", name="document_template_version_positive"),
        Index("ix_document_templates_tenant_key_active", "tenant_id", "key", "is_active"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    locale: Mapped[str] = mapped_column(String(8), nullable=False, default="en", server_default="en")
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")
    created_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )


class Document(TenantOwned, Base):
    """Issued PDF evidence; the payload captures the values used for rendering."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "document_number", name="uq_documents_tenant_number"),
        UniqueConstraint(
            "tenant_id", "kind", "reference_id", "template_version",
            name="uq_documents_reference_template_version",
        ),
        CheckConstraint(
            "kind IN ('DEMAND_LETTER','RECEIPT','STATEMENT')", name="document_kind_valid"
        ),
        CheckConstraint(
            "reference_type IN ('installment','receipt')", name="document_reference_type_valid"
        ),
        CheckConstraint("status IN ('DRAFT','ISSUED','VOIDED')", name="document_status_valid"),
        CheckConstraint(
            "review_state IN ('PENDING_REVIEW','APPROVED_FOR_SEND','APPROVED','VOIDED')",
            name="document_review_state_valid",
        ),
        CheckConstraint("template_version > 0", name="document_template_version_positive"),
        CheckConstraint("length(content_sha256) = 64", name="document_sha256_valid"),
        Index("ix_documents_tenant_kind_created", "tenant_id", "kind", "created_at"),
        Index("ix_documents_tenant_reference", "tenant_id", "reference_type", "reference_id"),
        Index("ix_documents_tenant_review_state", "tenant_id", "review_state"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_type: Mapped[str] = mapped_column(String(24), nullable=False)
    reference_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    template_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_templates.id", ondelete="SET NULL"), nullable=True
    )
    template_version: Mapped[int] = mapped_column(nullable=False)
    document_number: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DocumentStatus.DRAFT.value,
        server_default=DocumentStatus.DRAFT.value,
    )
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    issued_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_state: Mapped[str] = mapped_column(
        String(24), nullable=False, default=DocumentReviewState.APPROVED.value,
        server_default=DocumentReviewState.APPROVED.value,
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )
