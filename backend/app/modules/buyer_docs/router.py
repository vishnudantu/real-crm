"""BuyerVault staff and buyer-portal endpoints.

Staff routes keep the existing ADMIN/SALES_EXECUTIVE guard; the parallel
``/buyer-docs/mine/*`` surface admits BUYER accounts (and staff) and always
scopes to the server-resolved Contact for the authenticated user. Uploads use
raw bodies so python-multipart stays out of the dependency set.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import require_roles
from app.modules.buyer_docs import service
from app.modules.buyer_docs.models import (
    BuyerDocumentCategory,
    BuyerDocumentStatus,
    DocumentRequestStatus,
)
from app.modules.buyer_docs.schemas import (
    BuyerDocumentListResponse,
    BuyerDocumentResponse,
    BuyerDocumentReviewRequest,
    DocumentRequestCreate,
    DocumentRequestListResponse,
    DocumentRequestResponse,
)
from app.modules.customers.models import Contact
from app.modules.users.models import RoleName, User

router = APIRouter(prefix="/buyer-docs", tags=["buyer-docs"])
StaffUser = Annotated[
    User, Depends(require_roles(RoleName.ADMIN, RoleName.SALES_EXECUTIVE))
]
BuyerPortalUser = Annotated[
    User,
    Depends(require_roles(RoleName.ADMIN, RoleName.SALES_EXECUTIVE, RoleName.BUYER)),
]


def _buyer_contact(actor: User, db: Session) -> Contact:
    """Resolve the buyer's own contact or 404 — never trust client contact ids."""
    contact = service.resolve_buyer_contact(db, actor)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buyer contact not found.")
    return contact


@router.post(
    "/documents",
    response_model=BuyerDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a staff buyer document (raw image/* or PDF body)",
)
async def upload_document_endpoint(
    staff: StaffUser,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
    contact_id: UUID,
    category: BuyerDocumentCategory,
    title: Annotated[str, Query(min_length=1, max_length=255)],
    expiry_date: date | None = None,
) -> BuyerDocumentResponse:
    contents = await request.body()
    document = service.upload_document(
        db,
        actor=staff,
        contact_id=contact_id,
        category=category,
        title=title,
        contents=contents,
        content_type=request.headers.get("content-type", "application/octet-stream"),
        expiry_date=expiry_date,
    )
    return BuyerDocumentResponse.model_validate(document)


@router.get("/documents", response_model=BuyerDocumentListResponse)
def list_documents_endpoint(
    staff: StaffUser,
    db: Annotated[Session, Depends(get_db)],
    contact_id: UUID | None = None,
    category: BuyerDocumentCategory | None = None,
    document_status: Annotated[BuyerDocumentStatus | None, Query(alias="status")] = None,
) -> BuyerDocumentListResponse:
    rows = service.list_documents(
        db,
        tenant_id=staff.tenant_id,
        contact_id=contact_id,
        category=category,
        status=document_status,
        actor=staff,
    )
    return BuyerDocumentListResponse(items=rows, total=len(rows))


@router.get("/documents/{document_id}/download")
def download_document_endpoint(
    document_id: UUID,
    staff: StaffUser,
    db: Annotated[Session, Depends(get_db)],
):
    document, path = service.get_document_for_download(
        db,
        tenant_id=staff.tenant_id,
        document_id=document_id,
        actor=staff,
    )
    return FileResponse(
        path,
        media_type=document.content_type,
        headers={
            "X-Content-Sha256": document.content_sha256,
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/documents/{document_id}/review", response_model=BuyerDocumentResponse)
def review_document_endpoint(
    document_id: UUID,
    payload: BuyerDocumentReviewRequest,
    staff: StaffUser,
    db: Annotated[Session, Depends(get_db)],
) -> BuyerDocumentResponse:
    document = service.review_document(
        db,
        actor=staff,
        document_id=document_id,
        decision=payload.decision,
        review_note=payload.review_note,
    )
    return BuyerDocumentResponse.model_validate(document)


@router.post(
    "/requests",
    response_model=DocumentRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_request_endpoint(
    payload: DocumentRequestCreate,
    staff: StaffUser,
    db: Annotated[Session, Depends(get_db)],
) -> DocumentRequestResponse:
    request = service.create_request(db, actor=staff, **payload.model_dump())
    return DocumentRequestResponse.model_validate(request)


@router.get("/requests", response_model=DocumentRequestListResponse)
def list_requests_endpoint(
    staff: StaffUser,
    db: Annotated[Session, Depends(get_db)],
    contact_id: UUID | None = None,
    category: BuyerDocumentCategory | None = None,
    request_status: Annotated[DocumentRequestStatus | None, Query(alias="status")] = None,
) -> DocumentRequestListResponse:
    rows = service.list_requests(
        db,
        tenant_id=staff.tenant_id,
        contact_id=contact_id,
        category=category,
        status=request_status,
        actor=staff,
    )
    return DocumentRequestListResponse(items=rows, total=len(rows))


@router.post("/requests/{request_id}/cancel", response_model=DocumentRequestResponse)
def cancel_request_endpoint(
    request_id: UUID,
    staff: StaffUser,
    db: Annotated[Session, Depends(get_db)],
) -> DocumentRequestResponse:
    request = service.cancel_request(db, actor=staff, request_id=request_id)
    return DocumentRequestResponse.model_validate(request)


# --------------------------------------------------------------------------- #
# Buyer portal surface: /buyer-docs/mine/*
#
# Every route resolves the contact from the authenticated user (never from the
# request) and answers 404 — not 403 — when no buyer contact resolves or when
# the artifact belongs to someone else, so existence is never disclosed.
# --------------------------------------------------------------------------- #


@router.post(
    "/mine/documents",
    response_model=BuyerDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Buyer self-upload; owns the document and fulfills OPEN requests",
)
async def upload_buyer_document_endpoint(
    buyer: BuyerPortalUser,
    db: Annotated[Session, Depends(get_db)],
    request: Request,
    category: BuyerDocumentCategory,
    title: Annotated[str, Query(min_length=1, max_length=255)],
    expiry_date: date | None = None,
) -> BuyerDocumentResponse:
    contact = _buyer_contact(buyer, db)
    contents = await request.body()
    document = service.upload_buyer_document(
        db,
        actor=buyer,
        contact=contact,
        category=category,
        title=title,
        contents=contents,
        content_type=request.headers.get("content-type", "application/octet-stream"),
        expiry_date=expiry_date,
    )
    return BuyerDocumentResponse.model_validate(document)


@router.get("/mine/documents", response_model=BuyerDocumentListResponse)
def list_buyer_documents_endpoint(
    buyer: BuyerPortalUser,
    db: Annotated[Session, Depends(get_db)],
    category: BuyerDocumentCategory | None = None,
    document_status: Annotated[BuyerDocumentStatus | None, Query(alias="status")] = None,
) -> BuyerDocumentListResponse:
    contact = _buyer_contact(buyer, db)
    rows = service.list_buyer_documents(
        db,
        contact=contact,
        category=category,
        status=document_status,
    )
    return BuyerDocumentListResponse(items=rows, total=len(rows))


@router.get("/mine/documents/{document_id}/download")
def download_buyer_document_endpoint(
    document_id: UUID,
    buyer: BuyerPortalUser,
    db: Annotated[Session, Depends(get_db)],
):
    contact = _buyer_contact(buyer, db)
    document, path = service.get_buyer_document_for_download(
        db, contact=contact, document_id=document_id
    )
    return FileResponse(
        path,
        media_type=document.content_type,
        headers={
            "X-Content-Sha256": document.content_sha256,
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/mine/requests", response_model=DocumentRequestListResponse)
def list_buyer_requests_endpoint(
    buyer: BuyerPortalUser,
    db: Annotated[Session, Depends(get_db)],
    category: BuyerDocumentCategory | None = None,
) -> DocumentRequestListResponse:
    contact = _buyer_contact(buyer, db)
    rows = service.list_buyer_open_requests(db, contact=contact, category=category)
    return DocumentRequestListResponse(items=rows, total=len(rows))
