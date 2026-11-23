"""Bank transaction ingestion and deterministic reconciliation matching.

Matching is suggestion-only: a confirmed UTR-exact match sets MATCHED and links
to the receipt's installment, while a unique-amount match is recorded as a
pending suggestion that leaves status UNMATCHED. No receipts are created and no
installment balances change here — ledger posting is out of scope.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.postsales import repository as postsales_repository
from app.modules.postsales.models import Installment, Receipt
from app.modules.reconciliation import repository
from app.modules.reconciliation.exceptions import TransactionNotFoundError
from app.modules.reconciliation.models import (
    BankTransaction,
    TransactionStatus,
)

MATCH_UTR_RECEIPT = "UTR_RECEIPT"
MATCH_AMOUNT_UNIQUE = "AMOUNT_UNIQUE"


def ingest_rows(
    session: Session, *, actor, account_label: str, rows: list[dict]
) -> dict:
    """Import statement rows; a duplicate (account_label, utr) is skipped."""
    created = 0
    duplicates = 0
    errors: list[str] = []
    for row in rows:
        utr = row["utr"]
        existing = repository.get_by_utr(
            session, tenant_id=actor.tenant_id, account_label=account_label, utr=utr
        )
        if existing is not None:
            duplicates += 1
            continue
        txn = BankTransaction(
            tenant_id=actor.tenant_id,
            account_label=account_label,
            utr=utr,
            amount_paise=row["amount_paise"],
            txn_date=row["txn_date"],
            payer_name=row.get("payer_name"),
            payer_detail=row.get("payer_detail"),
            raw={**row, "txn_date": str(row["txn_date"])},
            status=TransactionStatus.UNMATCHED.value,
        )
        session.add(txn)
        created += 1
    session.commit()
    return {"created": created, "duplicates": duplicates, "errors": errors}


def _open_installments_with_outstanding(
    session: Session, *, tenant_id: UUID
) -> list[tuple[Installment, int]]:
    """Return (installment, outstanding_paise) for every open installment."""
    installments = list(
        session.scalars(
            select(Installment).where(
                Installment.tenant_id == tenant_id,
                Installment.status.in_(postsales_repository.OPEN_INSTALLMENT_STATUSES),
            )
        ).all()
    )
    result: list[tuple[Installment, int]] = []
    for inst in installments:
        paid = postsales_repository.receipt_total_for_installment(
            session, inst.id, tenant_id=tenant_id
        )
        outstanding = inst.amount_paise - paid
        if outstanding > 0:
            result.append((inst, outstanding))
    return result


def _receipt_installment_for_utr(
    session: Session, *, tenant_id: UUID, utr: str
) -> UUID | None:
    """Installment id of the receipt whose reference equals the UTR."""
    receipt = session.scalar(
        select(Receipt).where(
            Receipt.tenant_id == tenant_id,
            Receipt.reference == utr,
            Receipt.voided_at.is_(None),
        )
    )
    return receipt.installment_id if receipt is not None else None


def suggest_matches(session: Session, *, actor) -> dict:
    """Deterministically match each UNMATCHED transaction.

    (a) exact UTR == a live receipt.reference -> MATCHED, linked to that
        receipt's installment (matched_by=UTR_RECEIPT);
    (b) else if the amount equals exactly one open installment's outstanding,
        record a suggestion (matched_by=AMOUNT_UNIQUE) but keep status UNMATCHED;
    (c) else leave UNMATCHED in the exception queue, PRESERVING any earlier
        AMOUNT_UNIQUE suggestion: provenance set by a previous run is never
        cleared silently, only overwritten when this pass finds a (better)
        match. A human still confirms or ignores every suggestion.
    """
    unmatched = repository.list_unmatched(session, tenant_id=actor.tenant_id)
    open_with_outstanding = _open_installments_with_outstanding(
        session, tenant_id=actor.tenant_id
    )

    matched = 0
    suggested = 0
    still_unmatched = 0
    for txn in unmatched:
        installment_id = _receipt_installment_for_utr(
            session, tenant_id=actor.tenant_id, utr=txn.utr
        )
        if installment_id is not None:
            txn.status = TransactionStatus.MATCHED.value
            txn.matched_installment_id = installment_id
            txn.matched_by = MATCH_UTR_RECEIPT
            matched += 1
            session.add(txn)
            continue

        candidates = [
            inst for inst, outstanding in open_with_outstanding
            if outstanding == txn.amount_paise
        ]
        if len(candidates) == 1:
            txn.matched_installment_id = candidates[0].id
            txn.matched_by = MATCH_AMOUNT_UNIQUE
            suggested += 1
            session.add(txn)
            continue

        # No new match this pass: keep whatever AMOUNT_UNIQUE suggestion an
        # earlier pass recorded. Clearing it here would silently discard a
        # provenance a human may already be acting on.
        still_unmatched += 1

    session.commit()
    return {"matched": matched, "suggested": suggested, "still_unmatched": still_unmatched}


def list_transactions(
    session: Session, *, tenant_id: UUID, status: str | None = None,
    account_label: str | None = None,
) -> list[BankTransaction]:
    return repository.list_transactions(
        session, tenant_id=tenant_id, status=status, account_label=account_label
    )


def list_unmatched(session: Session, *, tenant_id: UUID) -> list[BankTransaction]:
    return repository.list_unmatched(session, tenant_id=tenant_id)


def ignore_transaction(
    session: Session, *, actor, transaction_id: UUID
) -> BankTransaction:
    txn = repository.get_transaction(session, transaction_id, tenant_id=actor.tenant_id)
    if txn is None:
        raise TransactionNotFoundError()
    txn.status = TransactionStatus.IGNORED.value
    session.add(txn)
    session.commit()
    session.refresh(txn)
    return txn
