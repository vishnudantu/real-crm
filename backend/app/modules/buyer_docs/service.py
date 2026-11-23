"""Buyer document upload, verification, expiry, and request lifecycle."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.buyer_docs.models import (
    BuyerDocument,
    BuyerDocumentCategory,
    BuyerDocumentStatus,
    DocumentRequest,
    DocumentRequestStatus,
    utcnow,
)
from app.modules.customers.models import (
    Contact,
    ContactMethod,
    ContactMethodKind,
    ContactStatus,
)
from app.modules.leads.schemas import normalize_email, normalize_phone
from app.modules.users.exceptions import InsufficientPermissionsError
from app.modules.users.models import RoleName, User

STAFF_ROLES = frozenset({RoleName.ADMIN.value, RoleName.SALES_EXECUTIVE.value})
REVIEWABLE_STATUSES = frozenset({
    BuyerDocumentStatus.SUBMITTED.value,
    BuyerDocumentStatus.UNDER_REVIEW.value,
})


def _require_staff(actor: User) -> None:
    if actor.role.name not in STAFF_ROLES:
        raise InsufficientPermissionsError()


def _category_value(category: BuyerDocumentCategory | str) -> str:
    try:
        return BuyerDocumentCategory(category).value
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid buyer document category.") from exc


def _check_actor_tenant(actor: User, tenant_id: UUID) -> None:
    _require_staff(actor)
    if actor.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buyer document resource not found.")


def _status_value(value: BuyerDocumentStatus | DocumentRequestStatus | str | None) -> str | None:
    return value.value if hasattr(value, "value") else value


def _contact_for_tenant(session: Session, *, tenant_id: UUID, contact_id: UUID) -> Contact:
    contact = session.scalar(
        select(Contact).where(Contact.id == contact_id, Contact.tenant_id == tenant_id)
    )
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found.")
    return contact


def _document_for_tenant(
    session: Session, *, tenant_id: UUID, document_id: UUID
) -> BuyerDocument:
    document = session.scalar(
        select(BuyerDocument).where(
            BuyerDocument.id == document_id, BuyerDocument.tenant_id == tenant_id
        )
    )
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buyer document not found.")
    return document


def _request_for_tenant(
    session: Session, *, tenant_id: UUID, request_id: UUID
) -> DocumentRequest:
    request = session.scalar(
        select(DocumentRequest).where(
            DocumentRequest.id == request_id, DocumentRequest.tenant_id == tenant_id
        )
    )
    if request is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document request not found.")
    return request


def _contact_ids_for_identity(
    session: Session, *, tenant_id: UUID, kind: str, normalized_value: str
) -> set[UUID]:
    """ACTIVE contact ids in the tenant whose method row matches the identity."""
    return set(
        session.scalars(
            select(ContactMethod.contact_id)
            .join(Contact, Contact.id == ContactMethod.contact_id)
            .where(
                ContactMethod.tenant_id == tenant_id,
                ContactMethod.kind == kind,
                ContactMethod.normalized_value == normalized_value,
                Contact.status == ContactStatus.ACTIVE.value,
            )
        ).all()
    )


def resolve_buyer_contact(session: Session, actor: User) -> Contact | None:
    """Resolve an authenticated account to its buyer Contact server-side.

    Matches the actor's normalized email (and phone, when present) against
    ContactMethod identity rows on ACTIVE contacts within the actor's tenant.
    Client-supplied contact ids are never consulted here. Returns ``None``
    when nothing matches or when the identities point at more than one
    contact (ambiguous); callers must treat ``None`` as "no buyer resources"
    and answer 404 rather than leaking which part matched.
    """
    contact_ids: set[UUID] = set()
    email = normalize_email(actor.email)
    if email:
        contact_ids |= _contact_ids_for_identity(
            session,
            tenant_id=actor.tenant_id,
            kind=ContactMethodKind.EMAIL.value,
            normalized_value=str(email),
        )
    if actor.phone:
        try:
            normalized_phone = normalize_phone(actor.phone)
        except ValueError:
            normalized_phone = None
        if normalized_phone:
            contact_ids |= _contact_ids_for_identity(
                session,
                tenant_id=actor.tenant_id,
                kind=ContactMethodKind.PHONE.value,
                normalized_value=normalized_phone,
            )
    if len(contact_ids) != 1:
        return None
    return session.scalar(
        select(Contact).where(
            Contact.id == next(iter(contact_ids)),
            Contact.tenant_id == actor.tenant_id,
            Contact.status == ContactStatus.ACTIVE.value,
        )
    )


def _validate_upload_payload(contents: bytes, content_type: str) -> str:
    """Return the normalized content type after allowlist/emptiness/size checks."""
    from app.modules.buyer_docs import storage

    normalized_content_type = (content_type or "application/octet-stream").split(";")[0].strip().lower()
    if normalized_content_type != "application/pdf" and not normalized_content_type.startswith("image/"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported buyer document content type: {normalized_content_type}.",
        )
    if not contents:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty buyer document file.")
    if len(contents) > storage.MAX_DOCUMENT_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Buyer document exceeds the 10 MB limit.")
    return normalized_content_type


def _store_document(
    session: Session,
    *,
    actor: User,
    contact: Contact,
    category: BuyerDocumentCategory | str,
    title: str,
    contents: bytes,
    normalized_content_type: str,
    expiry_date: date | None = None,
) -> BuyerDocument:
    """Persist bytes + row and fulfill matching OPEN requests atomically.

    Shared by staff and buyer self-upload paths; every guard (content type,
    size, exclusive create, tenant-prefixed path, request fulfillment) applies
    to both. The caller validates the payload and resolves the contact.
    """
    from app.modules.buyer_docs import storage

    category_value = _category_value(category)
    relative_path, digest = storage.write_document(
        tenant_id=contact.tenant_id, contents=contents
    )
    try:
        document = BuyerDocument(
            tenant_id=contact.tenant_id,
            contact_id=contact.id,
            category=category_value,
            title=title,
            storage_path=relative_path,
            content_sha256=digest,
            content_type=normalized_content_type,
            size_bytes=len(contents),
            status=BuyerDocumentStatus.SUBMITTED.value,
            uploaded_by_id=actor.id,
            expiry_date=expiry_date,
        )
        session.add(document)
        session.flush()
        now = utcnow()
        matching_requests = session.scalars(
            select(DocumentRequest)
            .where(
                DocumentRequest.tenant_id == contact.tenant_id,
                DocumentRequest.contact_id == contact.id,
                DocumentRequest.category == category_value,
                DocumentRequest.status == DocumentRequestStatus.OPEN.value,
            )
            .order_by(DocumentRequest.created_at, DocumentRequest.id)
            .with_for_update()
        ).all()
        for request in matching_requests:
            request.status = DocumentRequestStatus.FULFILLED.value
            request.updated_at = now
            session.add(request)
        session.commit()
        session.refresh(document)
        return document
    except Exception:
        session.rollback()
        storage.remove_document(relative_path)
        raise


def upload_document(
    session: Session,
    *,
    actor: User,
    contact_id: UUID,
    category: BuyerDocumentCategory | str,
    title: str,
    contents: bytes,
    content_type: str,
    expiry_date: date | None = None,
) -> BuyerDocument:
    """Store a staff artifact and fulfill matching open requests atomically."""
    _require_staff(actor)
    normalized_content_type = _validate_upload_payload(contents, content_type)
    contact = _contact_for_tenant(
        session, tenant_id=actor.tenant_id, contact_id=contact_id
    )
    return _store_document(
        session,
        actor=actor,
        contact=contact,
        category=category,
        title=title,
        contents=contents,
        normalized_content_type=normalized_content_type,
        expiry_date=expiry_date,
    )


def upload_buyer_document(
    session: Session,
    *,
    actor: User,
    contact: Contact,
    category: BuyerDocumentCategory | str,
    title: str,
    contents: bytes,
    content_type: str,
    expiry_date: date | None = None,
) -> BuyerDocument:
    """Buyer self-upload, always owned by the server-resolved contact.

    ``contact`` must come from :func:`resolve_buyer_contact` for the actor;
    the document can never be attributed to a client-chosen contact.
    """
    normalized_content_type = _validate_upload_payload(contents, content_type)
    return _store_document(
        session,
        actor=actor,
        contact=contact,
        category=category,
        title=title,
        contents=contents,
        normalized_content_type=normalized_content_type,
        expiry_date=expiry_date,
    )


def list_documents(
    session: Session,
    tenant_id: UUID,
    contact_id: UUID | None = None,
    category: BuyerDocumentCategory | str | None = None,
    status: BuyerDocumentStatus | str | None = None,
    *,
    actor: User | None = None,
) -> list[BuyerDocument]:
    """Return tenant documents with optional contact, category, and status filters."""
    if actor is not None:
        _check_actor_tenant(actor, tenant_id)
    statement = select(BuyerDocument).where(BuyerDocument.tenant_id == tenant_id)
    if contact_id is not None:
        statement = statement.where(BuyerDocument.contact_id == contact_id)
    if category is not None:
        statement = statement.where(BuyerDocument.category == _category_value(category))
    if status is not None:
        statement = statement.where(BuyerDocument.status == _status_value(status))
    return list(session.scalars(statement.order_by(BuyerDocument.created_at.desc(), BuyerDocument.id)).unique().all())


def review_document(
    session: Session,
    *,
    actor: User,
    document_id: UUID,
    decision: BuyerDocumentStatus | str,
    review_note: str | None = None,
) -> BuyerDocument:
    """Decide only SUBMITTED or UNDER_REVIEW artifacts without stale overwrites."""
    _require_staff(actor)
    decision_value = _status_value(decision)
    if decision_value not in (BuyerDocumentStatus.VERIFIED.value, BuyerDocumentStatus.REJECTED.value):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Decision must be VERIFIED or REJECTED.")
    document = _document_for_tenant(
        session, tenant_id=actor.tenant_id, document_id=document_id
    )
    if document.status not in REVIEWABLE_STATUSES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This buyer document cannot be reviewed.")
    now = utcnow()
    result = session.execute(
        update(BuyerDocument)
        .where(
            BuyerDocument.id == document.id,
            BuyerDocument.tenant_id == actor.tenant_id,
            BuyerDocument.status.in_(REVIEWABLE_STATUSES),
        )
        .values(
            status=decision_value,
            verified_by_id=actor.id,
            reviewed_at=now,
            review_note=review_note,
            updated_at=now,
        )
    )
    if result.rowcount == 0:
        session.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This buyer document cannot be reviewed.")
    session.commit()
    session.refresh(document)
    return document


def mark_expired(session: Session, now: datetime | date) -> int:
    """Mark verified artifacts expired strictly before the supplied UTC date."""
    today = now.date() if isinstance(now, datetime) else now
    result = session.execute(
        update(BuyerDocument)
        .where(
            BuyerDocument.status == BuyerDocumentStatus.VERIFIED.value,
            BuyerDocument.expiry_date.is_not(None),
            BuyerDocument.expiry_date < today,
        )
        .values(status=BuyerDocumentStatus.EXPIRED.value, updated_at=utcnow())
    )
    session.commit()
    return result.rowcount or 0


def create_request(
    session: Session,
    *,
    actor: User,
    contact_id: UUID,
    category: BuyerDocumentCategory | str,
    title: str,
    due_date: date | None = None,
    notes: str | None = None,
) -> DocumentRequest:
    _require_staff(actor)
    contact = _contact_for_tenant(session, tenant_id=actor.tenant_id, contact_id=contact_id)
    request = DocumentRequest(
        tenant_id=actor.tenant_id,
        contact_id=contact.id,
        category=_category_value(category),
        title=title,
        due_date=due_date,
        notes=notes,
        status=DocumentRequestStatus.OPEN.value,
        created_by_id=actor.id,
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


def list_requests(
    session: Session,
    tenant_id: UUID,
    contact_id: UUID | None = None,
    category: BuyerDocumentCategory | str | None = None,
    status: DocumentRequestStatus | str | None = None,
    *,
    actor: User | None = None,
) -> list[DocumentRequest]:
    if actor is not None:
        _check_actor_tenant(actor, tenant_id)
    statement = select(DocumentRequest).where(DocumentRequest.tenant_id == tenant_id)
    if contact_id is not None:
        statement = statement.where(DocumentRequest.contact_id == contact_id)
    if category is not None:
        statement = statement.where(DocumentRequest.category == _category_value(category))
    if status is not None:
        statement = statement.where(DocumentRequest.status == _status_value(status))
    return list(session.scalars(statement.order_by(DocumentRequest.created_at.desc(), DocumentRequest.id)).unique().all())


def cancel_request(session: Session, *, actor: User, request_id: UUID) -> DocumentRequest:
    _require_staff(actor)
    request = _request_for_tenant(session, tenant_id=actor.tenant_id, request_id=request_id)
    if request.status != DocumentRequestStatus.OPEN.value:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only OPEN document requests can be cancelled.")
    result = session.execute(
        update(DocumentRequest)
        .where(
            DocumentRequest.id == request.id,
            DocumentRequest.tenant_id == actor.tenant_id,
            DocumentRequest.status == DocumentRequestStatus.OPEN.value,
        )
        .values(status=DocumentRequestStatus.CANCELLED.value, updated_at=utcnow())
    )
    if result.rowcount == 0:
        session.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only OPEN document requests can be cancelled.")
    session.commit()
    session.refresh(request)
    return request


def get_document_for_download(
    session: Session,
    tenant_id: UUID,
    document_id: UUID,
    *,
    actor: User | None = None,
) -> tuple[BuyerDocument, Path]:
    """Return tenant-checked metadata and validated absolute local path."""
    from app.modules.buyer_docs import storage

    if actor is not None:
        _check_actor_tenant(actor, tenant_id)
    document = _document_for_tenant(
        session, tenant_id=tenant_id, document_id=document_id
    )
    return document, _validated_download_path(document)


def _validated_download_path(document: BuyerDocument) -> Path:
    """Resolve the stored relative path, enforcing storage invariants."""
    from app.modules.buyer_docs import storage

    try:
        path = storage.resolve_path(document.storage_path)
    except ValueError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Invalid buyer document path.") from exc
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buyer document file not found.")
    return path


def list_buyer_documents(
    session: Session,
    *,
    contact: Contact,
    category: BuyerDocumentCategory | str | None = None,
    status: BuyerDocumentStatus | str | None = None,
) -> list[BuyerDocument]:
    """Buyer-scoped listing: only artifacts owned by the resolved contact."""
    return list_documents(
        session,
        tenant_id=contact.tenant_id,
        contact_id=contact.id,
        category=category,
        status=status,
    )


def get_buyer_document_for_download(
    session: Session, *, contact: Contact, document_id: UUID
) -> tuple[BuyerDocument, Path]:
    """Download only a document belonging to the resolved contact, else 404."""
    document = _document_for_tenant(
        session, tenant_id=contact.tenant_id, document_id=document_id
    )
    if document.contact_id != contact.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buyer document not found.")
    return document, _validated_download_path(document)


def list_buyer_open_requests(
    session: Session,
    *,
    contact: Contact,
    category: BuyerDocumentCategory | str | None = None,
) -> list[DocumentRequest]:
    """OPEN document requests targeting the resolved contact only."""
    return list_requests(
        session,
        tenant_id=contact.tenant_id,
        contact_id=contact.id,
        category=category,
        status=DocumentRequestStatus.OPEN.value,
    )
