"""BuyerVault request and response contracts; absolute paths are never exposed."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.buyer_docs.models import (
    BuyerDocumentCategory,
    BuyerDocumentStatus,
    DocumentRequestStatus,
)


class BuyerDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contact_id: UUID | None
    category: BuyerDocumentCategory
    title: str
    content_sha256: str
    content_type: str
    size_bytes: int
    status: BuyerDocumentStatus
    uploaded_by_id: UUID | None
    verified_by_id: UUID | None
    reviewed_at: datetime | None
    review_note: str | None
    expiry_date: date | None
    created_at: datetime
    updated_at: datetime


class BuyerDocumentListResponse(BaseModel):
    items: list[BuyerDocumentResponse]
    total: int


class BuyerDocumentReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: Literal[BuyerDocumentStatus.VERIFIED, BuyerDocumentStatus.REJECTED]
    review_note: str | None = Field(default=None, max_length=2000)


class DocumentRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    contact_id: UUID
    category: BuyerDocumentCategory
    title: str = Field(min_length=1, max_length=255)
    due_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)


class DocumentRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contact_id: UUID
    category: BuyerDocumentCategory
    title: str
    status: DocumentRequestStatus
    due_date: date | None
    notes: str | None
    created_by_id: UUID | None
    created_at: datetime
    updated_at: datetime


class DocumentRequestListResponse(BaseModel):
    items: list[DocumentRequestResponse]
    total: int
