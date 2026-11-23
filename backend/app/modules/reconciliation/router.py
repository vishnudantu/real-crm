"""Reconciliation API: ingestion, match suggestions, and the exception queue."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import require_permission
from app.modules.reconciliation import service
from app.modules.reconciliation.schemas import (
    BankTransactionResponse,
    IngestRequest,
    IngestResponse,
    SuggestMatchesResponse,
    TransactionListResponse,
)
from app.modules.users.models import User
from app.modules.users.permissions import RECONCILIATION_READ, RECONCILIATION_WRITE

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])

# Staff read surfaces map to reconciliation.read; admin-only writes map to
# reconciliation.write.
ReadUser = Annotated[User, Depends(require_permission(RECONCILIATION_READ))]
WriteUser = Annotated[User, Depends(require_permission(RECONCILIATION_WRITE))]


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_endpoint(
    payload: IngestRequest,
    admin: WriteUser,
    db: Annotated[Session, Depends(get_db)],
):
    rows = [row.model_dump() for row in payload.rows]
    return service.ingest_rows(
        db, actor=admin, account_label=payload.account_label, rows=rows
    )


@router.post("/suggest-matches", response_model=SuggestMatchesResponse)
def suggest_matches_endpoint(
    admin: WriteUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.suggest_matches(db, actor=admin)


@router.get("/transactions", response_model=TransactionListResponse)
def list_transactions_endpoint(
    read_user: ReadUser,
    db: Annotated[Session, Depends(get_db)],
    txn_status: Annotated[str | None, Query(alias="status")] = None,
    account_label: str | None = None,
):
    rows = service.list_transactions(
        db, tenant_id=read_user.tenant_id, status=txn_status, account_label=account_label
    )
    return TransactionListResponse(items=rows, total=len(rows))


@router.get("/unmatched", response_model=TransactionListResponse)
def list_unmatched_endpoint(
    read_user: ReadUser,
    db: Annotated[Session, Depends(get_db)],
):
    rows = service.list_unmatched(db, tenant_id=read_user.tenant_id)
    return TransactionListResponse(items=rows, total=len(rows))


@router.post("/transactions/{transaction_id}/ignore", response_model=BankTransactionResponse)
def ignore_transaction_endpoint(
    transaction_id: UUID,
    admin: WriteUser,
    db: Annotated[Session, Depends(get_db)],
):
    return service.ignore_transaction(db, actor=admin, transaction_id=transaction_id)
