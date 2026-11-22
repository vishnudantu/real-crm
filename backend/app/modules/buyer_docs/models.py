"""Tenant-owned buyer document artifacts and collection requests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.tenancy import TenantOwned


class BuyerDocumentCategory(StrEnum):
    IDENTITY = "IDENTITY"
    ADDRESS = "ADDRESS"
    INCOME = "INCOME"
    BANK = "BANK"
    LOAN = "LOAN"
    PROPERTY = "PROPERTY"
    AGREEMENT = "AGREEMENT"
    PAYMENT = "PAYMENT"
    REGISTRATION = "REGISTRATION"
    POSSESSION = "POSSESSION"
    OTHER = "OTHER"


class BuyerDocumentStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class DocumentRequestStatus(StrEnum):
    OPEN = "OPEN"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"


def utcnow() -> datetime:
    return datetime.now(UTC)


def _quoted_values(values: type[StrEnum]) -> str:
    return ", ".join(f"'{value.value}'" for value in values)


class BuyerDocument(TenantOwned, Base):
    """A staff-uploaded document with verification and optional expiry metadata."""

    __tablename__ = "buyer_documents"
    __table_args__ = (
        CheckConstraint(
            f"category IN ({_quoted_values(BuyerDocumentCategory)})",
            name="buyer_document_category_valid",
        ),
        CheckConstraint(
            f"status IN ({_quoted_values(BuyerDocumentStatus)})",
            name="buyer_document_status_valid",
        ),
        CheckConstraint("length(content_sha256) = 64", name="buyer_document_sha256_valid"),
        CheckConstraint("size_bytes > 0", name="buyer_document_size_positive"),
        Index("ix_buyer_documents_tenant_status", "tenant_id", "status"),
        Index("ix_buyer_documents_tenant_category", "tenant_id", "category"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    contact_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=BuyerDocumentStatus.SUBMITTED.value,
        server_default=BuyerDocumentStatus.SUBMITTED.value,
    )
    uploaded_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )


class DocumentRequest(TenantOwned, Base):
    """A staff request fulfilled by a matching buyer contact and category upload."""

    __tablename__ = "document_requests"
    __table_args__ = (
        CheckConstraint(
            f"category IN ({_quoted_values(BuyerDocumentCategory)})",
            name="document_request_category_valid",
        ),
        CheckConstraint(
            f"status IN ({_quoted_values(DocumentRequestStatus)})",
            name="document_request_status_valid",
        ),
        Index("ix_document_requests_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    contact_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DocumentRequestStatus.OPEN.value,
        server_default=DocumentRequestStatus.OPEN.value,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now(),
        onupdate=utcnow,
    )
