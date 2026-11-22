"""Tenant-scoped document persistence and MAX-based number allocation."""

from __future__ import annotations

import hashlib
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.documents.models import Document, DocumentTemplate

KIND_PREFIXES = {
    "DEMAND_LETTER": "DOC-DEMAND",
    "RECEIPT": "DOC-RECEIPT",
    "STATEMENT": "DOC-STATEMENT",
}


def lock_document_allocation(session: Session, *, tenant_id: UUID) -> None:
    """Serialize number allocation within a tenant on PostgreSQL."""

    if session.get_bind().dialect.name != "postgresql":
        return
    digest = hashlib.blake2b(f"documents:{tenant_id}".encode(), digest_size=8).digest()
    session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": int.from_bytes(digest, "big", signed=True)},
    )


def highest_document_sequence(session: Session, *, tenant_id: UUID, kind: str) -> int:
    """Return MAX numeric suffix for one document kind, never a row count."""

    prefix = KIND_PREFIXES[kind]
    numbers = session.scalars(
        select(Document.document_number).where(
            Document.tenant_id == tenant_id, Document.kind == kind
        )
    ).all()
    highest = 0
    for number in numbers:
        value, _, digits = (number or "").rpartition("-")
        if value == prefix and digits.isdigit():
            highest = max(highest, int(digits))
    return highest


def next_document_number(session: Session, *, tenant_id: UUID, kind: str) -> str:
    sequence = highest_document_sequence(session, tenant_id=tenant_id, kind=kind) + 1
    return f"{KIND_PREFIXES[kind]}-{sequence:06d}"


def active_template(session: Session, *, tenant_id: UUID, key: str) -> DocumentTemplate | None:
    return session.scalar(
        select(DocumentTemplate)
        .where(
            DocumentTemplate.tenant_id == tenant_id,
            DocumentTemplate.key == key,
            DocumentTemplate.is_active.is_(True),
        )
        .order_by(DocumentTemplate.version.desc())
        .limit(1)
    )


def document_for_reference(
    session: Session, *, tenant_id: UUID, kind: str, reference_id: UUID, template_version: int
) -> Document | None:
    return session.scalar(
        select(Document).where(
            Document.tenant_id == tenant_id,
            Document.kind == kind,
            Document.reference_id == reference_id,
            Document.template_version == template_version,
        )
    )


def get_document(session: Session, document_id: UUID, *, tenant_id: UUID) -> Document | None:
    return session.scalar(
        select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id)
    )


def list_documents(
    session: Session, *, tenant_id: UUID, kind: str | None = None, reference_id: UUID | None = None
) -> list[Document]:
    conditions = [Document.tenant_id == tenant_id]
    if kind is not None:
        conditions.append(Document.kind == kind)
    if reference_id is not None:
        conditions.append(Document.reference_id == reference_id)
    return list(
        session.scalars(
            select(Document).where(*conditions).order_by(Document.created_at.desc(), Document.id)
        ).all()
    )
