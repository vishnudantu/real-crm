"""Documents API: demand-letter/receipt issuance, listing, download, voiding.

Access is staff-role scoped for now (ADMIN and SALES_EXECUTIVE can read and
download; ADMIN issues and voids). Buyer-scoped download — where a customer
fetches only their own installment/receipt documents — arrives with the
buyer-passport work later and intentionally reuses these endpoints through a
tenant+customer predicate; until then buyers receive no access here.

Files are never addressed by client-supplied paths: every artifact is streamed
from the tenant-partitioned storage root through its database row only, and
no absolute path is exposed in any response.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import AdminUser, require_roles
from app.modules.documents import service
from app.modules.documents.schemas import (
    DocumentListResponse,
    DocumentProofResponse,
    DocumentResponse,
    DocumentVoidRequest,
)
from app.modules.users.models import RoleName, User

router = APIRouter(prefix="/documents", tags=["documents"])

DocumentStaffUser = Annotated[
    User,
    Depends(require_roles(RoleName.ADMIN, RoleName.SALES_EXECUTIVE)),
]


@router.post("/demand-letters/{installment_id}", response_model=DocumentResponse,
             status_code=status.HTTP_201_CREATED)
def issue_demand_letter_endpoint(
    installment_id: UUID,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    """Generate (or return the already-issued) demand-letter document for one
    installment at its active template version. Idempotent per reference."""

    return service.issue_demand_letter(db, actor=admin, installment_id=installment_id)


@router.post("/receipts/{receipt_id}/pdf", response_model=DocumentResponse,
             status_code=status.HTTP_201_CREATED)
def issue_receipt_pdf_endpoint(
    receipt_id: UUID,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    """Generate the PDF receipt document for an existing ledger receipt."""

    return service.issue_receipt_pdf(db, actor=admin, receipt_id=receipt_id)


@router.get("", response_model=DocumentListResponse)
def list_documents_endpoint(
    staff: DocumentStaffUser,
    db: Annotated[Session, Depends(get_db)],
    kind: Annotated[str | None, Query(max_length=32)] = None,
    reference_id: UUID | None = None,
):
    rows = service.list_documents(
        db, tenant_id=staff.tenant_id, kind=kind, reference_id=reference_id
    )
    return DocumentListResponse(items=rows, total=len(rows))


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document_endpoint(
    document_id: UUID,
    staff: DocumentStaffUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.get_document(db, document_id, tenant_id=staff.tenant_id)


@router.get("/{document_id}/download")
def download_document_endpoint(
    document_id: UUID,
    staff: DocumentStaffUser,
    db: Annotated[Session, Depends(get_db)],
):
    document, path = service.get_document_for_download(
        db, document_id, tenant_id=staff.tenant_id
    )
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{document.document_number}.pdf",
        headers={
            "X-Content-Type-Options": "nosniff",
            "X-Document-Sha256": document.content_sha256,
        },
    )


@router.post("/{document_id}/void", response_model=DocumentResponse)
def void_document_endpoint(
    document_id: UUID,
    payload: DocumentVoidRequest,
    admin: AdminUser,
    db: Annotated[Session, Depends(get_db)],
):
    """Void an issued document. The stored bytes remain for audit; downloads
    then return 410 with the recorded reason."""

    return service.mark_void(db, actor=admin, document_id=document_id, reason=payload.reason)


@router.get("/{document_id}/proof", response_model=DocumentProofResponse)
def document_proof_endpoint(
    document_id: UUID,
    staff: DocumentStaffUser,
    db: Annotated[Session, Depends(get_db)],
):
    """Evidence proof: number, hash, issuer, status and the fully materialized
    merge context used at issue time (bank account numbers stay masked)."""

    document = service.get_document(db, document_id, tenant_id=staff.tenant_id)
    return document
