"""Reconciliation contracts: ingestion requests and transaction responses."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.reconciliation.models import TransactionStatus


class BankRow(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    utr: str = Field(min_length=1, max_length=128)
    amount_paise: int = Field(gt=0)
    txn_date: date
    payer_name: str | None = Field(default=None, max_length=255)
    payer_detail: str | None = Field(default=None, max_length=255)


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    account_label: str = Field(min_length=1, max_length=64)
    rows: list[BankRow] = Field(min_length=1, max_length=2000)


class IngestResponse(BaseModel):
    created: int
    duplicates: int
    errors: list[str]


class BankTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_label: str
    utr: str
    amount_paise: int
    txn_date: date
    payer_name: str | None
    payer_detail: str | None
    status: TransactionStatus
    matched_installment_id: UUID | None
    matched_by: str | None
    created_at: datetime
    updated_at: datetime


class TransactionListResponse(BaseModel):
    items: list[BankTransactionResponse]
    total: int


class SuggestMatchesResponse(BaseModel):
    matched: int
    suggested: int
    still_unmatched: int
