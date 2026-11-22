"""Public API contracts for document issuance and evidence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.documents.models import DocumentStatus, DocumentTemplateKey


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: DocumentTemplateKey
    reference_type: str
    reference_id: UUID
    template_id: UUID | None
    template_version: int
    document_number: str
    status: DocumentStatus
    content_sha256: str
    issued_by: UUID | None
    issued_at: datetime | None
    voided_at: datetime | None
    void_reason: str | None
    created_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int


class DocumentVoidRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=2000)


class DocumentProofResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_number: str
    content_sha256: str
    status: DocumentStatus
    template_version: int
    issued_at: datetime | None
    issued_by: UUID | None
    voided_at: datetime | None
    void_reason: str | None
    payload_snapshot: dict
