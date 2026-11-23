"""Bank reconciliation: ingestion, deterministic match suggestions, exceptions.

Covers: ingest + duplicate protection, UTR-exact receipt matching, unique-amount
suggestion (no auto-post), the unmatched exception queue, ignore, and cross-tenant
isolation. Ledger auto-posting is explicitly out of scope.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.postsales import service as postsales_service
from app.modules.postsales.models import (
    Installment,
    PaymentPlanType,
    ReceiptChannel,
)
from app.modules.postsales.schemas import (
    InstallmentSpec,
    PaymentPlanCreateRequest,
    ReceiptCreateRequest,
    SaleBookingCreateRequest,
)
from app.modules.projects.models import Project, ProjectStatus
from app.modules.reconciliation.models import BankTransaction, TransactionStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
from app.modules.auth.security import hash_password
from tests.support import TEST_PASSWORD


@pytest.fixture()
def env(
    client: TestClient,
    override_db: None,
    test_session_factory: sessionmaker[Session],
    user_factory,
    auth_headers,
) -> dict:
    admin = user_factory(role=RoleName.ADMIN)
    headers = auth_headers(admin.email)
    with test_session_factory() as s:
        project = Project(
            tenant_id=admin.tenant_id,
            name="P",
            slug=f"p-{uuid4().hex[:8]}",
            location="X",
            status=ProjectStatus.ACTIVE.value,
            created_by=admin.id,
        )
        s.add(project)
        s.flush()
        lead = Lead(
            tenant_id=admin.tenant_id,
            full_name="Payer One",
            email="payer@finance.example",
            phone=f"91{uuid4().int % 10**10:010d}",
            project_id=project.id,
            source=LeadSource.WEBSITE.value,
            status=LeadStatus.CONVERTED.value,
            consent_to_contact=True,
        )
        s.add(lead)
        s.commit()
        return {
            "factory": test_session_factory,
            "tenant_id": admin.tenant_id,
            "admin_id": admin.id,
            "admin_email": admin.email,
            "headers": headers,
            "project_id": project.id,
            "lead_id": lead.id,
        }


def _booked_plan(env: dict, amount_paise: int, lead_id=None) -> str:
    """Create booking -> plan -> single installment via postsales.service."""
    with env["factory"]() as s:
        admin = s.get(User, env["admin_id"])
        lead = s.get(Lead, lead_id or env["lead_id"]) or Lead(
            id=lead_id,
            tenant_id=admin.tenant_id,
            full_name="Payer One",
            email="payer@finance.example",
            phone=f"91{uuid4().int % 10**10:010d}",
            project_id=env["project_id"],
            source=LeadSource.WEBSITE.value,
            status=LeadStatus.CONVERTED.value,
            consent_to_contact=True,
        )
        s.add(lead)
        s.flush()
        booking = postsales_service.create_booking(
            s,
            actor=admin,
            payload=SaleBookingCreateRequest(
                lead_id=lead.id,
                unit_number=f"U-{uuid4().hex[:6]}",
                consideration_paise=amount_paise,
            ),
        )
        plan = postsales_service.create_plan(
            s,
            actor=admin,
            booking_id=booking.id,
            payload=PaymentPlanCreateRequest(
                name="Single",
                plan_type=PaymentPlanType.TIME_LINKED,
                installments=[
                    InstallmentSpec(
                        milestone="Full",
                        amount_paise=amount_paise,
                        due_on=date.today(),
                    )
                ],
            ),
        )
        return str(plan.installments[0].id)


def _ingest(client: TestClient, env: dict, utr: str, amount: int, label: str = "HDFC-CA"):
    return client.post(
        "/api/v1/reconciliation/ingest",
        json={
            "account_label": label,
            "rows": [
                {
                    "utr": utr,
                    "amount_paise": amount,
                    "txn_date": "2026-01-05",
                    "payer_name": "Payer One",
                    "payer_detail": "payer@upi",
                }
            ],
        },
        headers=env["headers"],
    )


def test_ingest_creates_and_skips_duplicates(client: TestClient, env) -> None:
    r = _ingest(client, env, "UTR-AAA", 100_00)
    assert r.status_code == 201, r.text
    assert r.json()["created"] == 1
    assert r.json()["duplicates"] == 0
    assert r.json()["errors"] == []

    # Same account_label + utr is a duplicate, not an error.
    r2 = _ingest(client, env, "UTR-AAA", 100_00)
    assert r2.status_code == 201, r2.text
    assert r2.json()["created"] == 0
    assert r2.json()["duplicates"] == 1

    with env["factory"]() as s:
        rows = s.scalars(select(BankTransaction).where(BankTransaction.utr == "UTR-AAA")).all()
        assert len(rows) == 1
        assert rows[0].status == TransactionStatus.UNMATCHED.value


def test_utr_exact_match_links_to_receipt_installment(client: TestClient, env) -> None:
    installment_id = _booked_plan(env, 50_00_00)
    # Post a receipt with a known reference (the UTR).
    with env["factory"]() as s:
        admin = s.get(User, env["admin_id"])
        postsales_service.record_receipt(
            s,
            actor=admin,
            payload=ReceiptCreateRequest(
                installment_id=__import__("uuid").UUID(installment_id),
                amount_paise=10_00_00,
                channel=ReceiptChannel.UPI,
                reference="UTR-MATCH-1",
            ),
        )

    _ingest(client, env, "UTR-MATCH-1", 10_00_00)
    r = client.post("/api/v1/reconciliation/suggest-matches", headers=env["headers"])
    assert r.status_code == 200, r.text
    assert r.json()["matched"] == 1

    with env["factory"]() as s:
        txn = s.scalars(select(BankTransaction).where(BankTransaction.utr == "UTR-MATCH-1")).one()
        assert txn.status == TransactionStatus.MATCHED.value
        assert txn.matched_by == "UTR_RECEIPT"
        assert str(txn.matched_installment_id) == installment_id


def test_unique_amount_suggestion_does_not_autopost(client: TestClient, env) -> None:
    installment_id = _booked_plan(env, 75_00_00)
    _ingest(client, env, "UTR-AMT-1", 75_00_00)

    r = client.post("/api/v1/reconciliation/suggest-matches", headers=env["headers"])
    assert r.status_code == 200, r.text
    assert r.json()["matched"] == 0
    assert r.json()["suggested"] == 1

    with env["factory"]() as s:
        txn = s.scalars(select(BankTransaction).where(BankTransaction.utr == "UTR-AMT-1")).one()
        # Suggestion only: still UNMATCHED, no ledger mutation.
        assert txn.status == TransactionStatus.UNMATCHED.value
        assert str(txn.matched_installment_id) == installment_id
        assert txn.matched_by == "AMOUNT_UNIQUE"
        # The installment must NOT be marked paid.
        inst = s.get(Installment, __import__("uuid").UUID(installment_id))
        assert inst.status != "PAID"


def test_previous_amount_unique_suggestion_is_not_cleared_silently(
    client: TestClient, env
) -> None:
    """A later pass without a unique match keeps the AMOUNT_UNIQUE provenance."""
    installment_id = _booked_plan(env, 60_00_00)
    _ingest(client, env, "UTR-KEEP-1", 60_00_00)

    first = client.post("/api/v1/reconciliation/suggest-matches", headers=env["headers"])
    assert first.status_code == 200, first.text
    assert first.json()["suggested"] == 1

    # Drift: a second installment with the SAME outstanding makes the amount
    # ambiguous, so the next pass finds no unique match for this txn.
    _booked_plan(env, 60_00_00, lead_id=uuid4())
    second = client.post("/api/v1/reconciliation/suggest-matches", headers=env["headers"])
    assert second.status_code == 200, second.text
    assert second.json()["suggested"] == 0
    assert second.json()["matched"] == 0

    with env["factory"]() as s:
        txn = s.scalars(select(BankTransaction).where(BankTransaction.utr == "UTR-KEEP-1")).one()
        # The earlier suggestion survives: same installment, same matched_by.
        assert txn.status == TransactionStatus.UNMATCHED.value
        assert str(txn.matched_installment_id) == installment_id
        assert txn.matched_by == "AMOUNT_UNIQUE"

    # An exact UTR match still upgrades the suggestion in place.
    with env["factory"]() as s:
        admin = s.get(User, env["admin_id"])
        postsales_service.record_receipt(
            s,
            actor=admin,
            payload=ReceiptCreateRequest(
                installment_id=__import__("uuid").UUID(installment_id),
                amount_paise=60_00_00,
                channel=ReceiptChannel.UPI,
                reference="UTR-KEEP-1",
            ),
        )
    third = client.post("/api/v1/reconciliation/suggest-matches", headers=env["headers"])
    assert third.status_code == 200, third.text
    assert third.json()["matched"] == 1
    with env["factory"]() as s:
        txn = s.scalars(select(BankTransaction).where(BankTransaction.utr == "UTR-KEEP-1")).one()
        assert txn.status == TransactionStatus.MATCHED.value
        assert txn.matched_by == "UTR_RECEIPT"


def test_unmatched_stays_in_exception_queue(client: TestClient, env) -> None:
    _ingest(client, env, "UTR-ORPHAN", 12_34_56)
    r = client.post("/api/v1/reconciliation/suggest-matches", headers=env["headers"])
    assert r.json()["matched"] == 0
    assert r.json()["suggested"] == 0

    q = client.get("/api/v1/reconciliation/unmatched", headers=env["headers"])
    assert q.status_code == 200, q.text
    utrs = [t["utr"] for t in q.json()["items"]]
    assert "UTR-ORPHAN" in utrs


def test_ignore_transaction(client: TestClient, env) -> None:
    _ingest(client, env, "UTR-IGN", 5_00)
    txns = client.get("/api/v1/reconciliation/transactions", headers=env["headers"]).json()
    txn_id = next(t["id"] for t in txns["items"] if t["utr"] == "UTR-IGN")

    r = client.post(
        f"/api/v1/reconciliation/transactions/{txn_id}/ignore", headers=env["headers"]
    )
    assert r.status_code == 200, r.text

    with env["factory"]() as s:
        txn = s.get(BankTransaction, __import__("uuid").UUID(txn_id))
        assert txn.status == TransactionStatus.IGNORED.value

    # No longer in the unmatched queue.
    q = client.get("/api/v1/reconciliation/unmatched", headers=env["headers"]).json()
    assert "UTR-IGN" not in [t["utr"] for t in q["items"]]


def test_cross_tenant_isolation(client: TestClient, env, user_factory, auth_headers) -> None:
    _ingest(client, env, "UTR-ISO", 9_99)
    txns = client.get("/api/v1/reconciliation/transactions", headers=env["headers"]).json()
    txn_id = next(t["id"] for t in txns["items"] if t["utr"] == "UTR-ISO")

    # Another tenant's admin.
    with env["factory"]() as s:
        other = Tenant(slug=f"o-{uuid4().hex[:8]}", name="Other")
        s.add(other)
        s.commit()
    other_admin = user_factory(role=RoleName.ADMIN, tenant=_tenant_obj(env, other.slug))
    other_headers = auth_headers(other_admin.email)

    # Reads are tenant-scoped: the other tenant cannot see our transaction.
    lst = client.get("/api/v1/reconciliation/transactions", headers=other_headers).json()
    assert "UTR-ISO" not in [t["utr"] for t in lst["items"]]

    # Cross-tenant ignore returns 404.
    r = client.post(
        f"/api/v1/reconciliation/transactions/{txn_id}/ignore", headers=other_headers
    )
    assert r.status_code == 404


def _tenant_obj(env: dict, slug: str) -> Tenant:
    with env["factory"]() as s:
        return s.scalars(select(Tenant).where(Tenant.slug == slug)).one()


def test_write_requires_admin(client: TestClient, env, user_factory, auth_headers) -> None:
    sales = user_factory(role=RoleName.SALES_EXECUTIVE, email=f"s-{uuid4().hex[:6]}@ex.com")
    headers = auth_headers(sales.email)
    r = client.post(
        "/api/v1/reconciliation/ingest",
        json={"account_label": "HDFC-CA", "rows": [{"utr": "X", "amount_paise": 1, "txn_date": "2026-01-01"}]},
        headers=headers,
    )
    assert r.status_code == 403
