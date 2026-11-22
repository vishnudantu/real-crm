"""P0.2 evidence: receipt posting is concurrency-safe, unique, and idempotent.

Blueprint acceptance criteria covered (21.1):
- concurrent posts against insufficient balance: exactly one succeeds.
- no duplicate receipt numbers under concurrency.
- repeated idempotency key returns the prior result without a new ledger entry.
- failed transaction leaves no partial mutation.
- number derived from highest issued sequence (deletions cannot cause reissue).
- tenant isolation on receipts.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.security import hash_password
from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.postsales import repository, service
from app.modules.postsales.exceptions import (
    InstallmentNotFoundError,
    ReceiptAmountExceedsOutstandingError,
)
from app.modules.postsales.models import (
    Installment,
    InstallmentStatus,
    PaymentPlanType,
    Receipt,
    ReceiptChannel,
)
from app.modules.postsales.schemas import (
    InstallmentSpec,
    PaymentPlanCreateRequest,
    ReceiptCreateRequest,
    SaleBookingCreateRequest,
)
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD


def _principal(user_id: UUID, tenant_id: UUID) -> SimpleNamespace:
    """Detached actor carrying only what record_receipt reads.

    Worker threads must not touch the shared in-memory SQLite connection for
    identity lookups (StaticPool hands every session the same DBAPI
    connection; only the service's locked write path is safe there). On real
    PostgreSQL CI, record_receipt's advisory lock provides the same guarantee
    across independent pooled connections.
    """

    return SimpleNamespace(id=user_id, tenant_id=tenant_id)


def _fixture(session: Session, *, slug: str | None = None) -> tuple[Tenant, User, Project, Lead]:
    tenant = Tenant(slug=slug or f"fin-{uuid4().hex[:8]}", name="Finance Co")
    session.add(tenant)
    session.flush()
    role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one_or_none()
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    admin = User(
        tenant_id=tenant.id, full_name="Finance Admin",
        email=f"fin.{tenant.id.hex[:10]}@finance.example",
        password_hash=hash_password(TEST_PASSWORD), role_id=role.id, is_active=True,
    )
    session.add(admin)
    session.flush()
    project = Project(
        tenant_id=tenant.id, name="Ledger Towers", slug=f"ledger-{tenant.id.hex[:8]}",
        location="Hyderabad", status=ProjectStatus.ACTIVE.value, created_by=admin.id,
    )
    session.add(project)
    session.flush()
    lead = Lead(
        tenant_id=tenant.id, full_name="Payer One", email="payer@finance.example",
        phone=f"91{uuid4().int % 10**10:010d}", project_id=project.id,
        source=LeadSource.WEBSITE.value, status=LeadStatus.CONVERTED.value,
        consent_to_contact=True,
    )
    session.add(lead)
    session.commit()
    return tenant, admin, project, lead


def _booked_plan(session: Session, admin: User, lead: Lead, amount_paise: int) -> Installment:
    booking = service.create_booking(
        session, actor=admin,
        payload=SaleBookingCreateRequest(
            lead_id=lead.id, unit_number=f"U-{uuid4().hex[:6]}",
            consideration_paise=amount_paise,
        ),
    )
    plan = service.create_plan(
        session, actor=admin, booking_id=booking.id,
        payload=PaymentPlanCreateRequest(
            name="Single", plan_type=PaymentPlanType.TIME_LINKED,
            installments=[InstallmentSpec(milestone="Full", amount_paise=amount_paise, due_on=date.today())],
        ),
    )
    return plan.installments[0]


class TestConcurrentPosting:
    def test_two_full_payments_one_winner(self, test_session_factory: sessionmaker[Session]) -> None:
        """Same installment, two concurrent full payments: one posts, one conflicts."""

        with test_session_factory() as session:
            _tenant, admin, _project, lead = _fixture(session)
            installment = _booked_plan(session, admin, lead, 10_00_00_00)
            principal = _principal(admin.id, admin.tenant_id)
            installment_id = installment.id

        def post(_: int) -> str:
            with test_session_factory() as worker:
                try:
                    service.record_receipt(
                        worker, actor=principal,
                        payload=ReceiptCreateRequest(
                            installment_id=installment_id, amount_paise=10_00_00_00,
                            channel=ReceiptChannel.UPI,
                        ),
                    )
                    return "posted"
                except ReceiptAmountExceedsOutstandingError:
                    return "conflict"
                except HTTPException as exc:
                    # The loser may observe the now-PAID installment (400).
                    assert exc.status_code in (400, 409), exc
                    return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = sorted(pool.map(post, range(2)))

        assert outcomes == ["conflict", "posted"], outcomes
        with test_session_factory() as session:
            rows = session.scalars(
                select(Receipt).where(Receipt.installment_id == installment_id)
            ).all()
            assert len(rows) == 1
            inst = session.get(Installment, installment_id)
            assert inst.status == InstallmentStatus.PAID.value

    def test_concurrent_receipt_numbers_are_unique(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        """Parallel posts to different installments never share a receipt number."""

        with test_session_factory() as session:
            _tenant, admin, _project, lead = _fixture(session)
            ids = []
            for _ in range(4):
                extra = Lead(
                    tenant_id=_tenant.id, full_name=f"Payer {_}",
                    email=f"payer{uuid4().hex[:6]}@finance.example",
                    phone=f"92{uuid4().int % 10**10:010d}", project_id=_project.id,
                    source=LeadSource.WEBSITE.value, status=LeadStatus.CONVERTED.value,
                    consent_to_contact=True,
                )
                session.add(extra)
                session.commit()
                ids.append(_booked_plan(session, admin, extra, 5_00_00_00).id)
            principal = _principal(admin.id, admin.tenant_id)

        def post(index: int) -> str:
            with test_session_factory() as worker:
                receipt = service.record_receipt(
                    worker, actor=principal,
                    payload=ReceiptCreateRequest(
                        installment_id=ids[index], amount_paise=5_00_00_00,
                        channel=ReceiptChannel.CHEQUE,
                    ),
                )
                return receipt.receipt_number

        with ThreadPoolExecutor(max_workers=4) as pool:
            numbers = list(pool.map(post, range(4)))

        assert len(set(numbers)) == 4, numbers
        with test_session_factory() as session:
            count = session.scalar(select(func.count()).select_from(Receipt))
            assert count == 4


class TestIdempotency:
    def test_repeated_key_returns_original_receipt(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            _tenant, admin, _project, lead = _fixture(session)
            installment = _booked_plan(session, admin, lead, 20_00_00_00)

            first = service.record_receipt(
                session, actor=admin,
                payload=ReceiptCreateRequest(
                    installment_id=installment.id, amount_paise=5_00_00_00,
                    channel=ReceiptChannel.UPI, idempotency_key="gateway-txn-abc",
                ),
            )
            second = service.record_receipt(
                session, actor=admin,
                payload=ReceiptCreateRequest(
                    installment_id=installment.id, amount_paise=5_00_00_00,
                    channel=ReceiptChannel.UPI, idempotency_key="gateway-txn-abc",
                ),
            )
            assert first.id == second.id
            session.expire_all()
            paid = repository.receipt_total_for_installment(
                session, installment.id, tenant_id=admin.tenant_id
            )
            assert paid == 5_00_00_00  # posted once, not twice

    def test_distinct_keys_post_distinct_receipts(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            _tenant, admin, _project, lead = _fixture(session)
            installment = _booked_plan(session, admin, lead, 20_00_00_00)
            for key in ("pay-1", "pay-2"):
                service.record_receipt(
                    session, actor=admin,
                    payload=ReceiptCreateRequest(
                        installment_id=installment.id, amount_paise=5_00_00_00,
                        channel=ReceiptChannel.NEFT, idempotency_key=key,
                    ),
                )
            session.expire_all()
            paid = repository.receipt_total_for_installment(
                session, installment.id, tenant_id=admin.tenant_id
            )
            assert paid == 10_00_00_00


class TestSequenceAllocation:
    def test_number_ignores_gaps_and_never_reissues(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        """A legacy row with a high number forces the next sequence above MAX."""

        with test_session_factory() as session:
            tenant, admin, _project, lead = _fixture(session)
            installment = _booked_plan(session, admin, lead, 30_00_00_00)
            # Simulate a historical receipt beyond where COUNT would land.
            session.add(
                Receipt(
                    tenant_id=tenant.id, installment_id=installment.id,
                    receipt_number="RCPT-000042", amount_paise=1,
                    channel=ReceiptChannel.CASH, paid_at=installment.created_at,
                )
            )
            session.commit()

            receipt = service.record_receipt(
                session, actor=admin,
                payload=ReceiptCreateRequest(
                    installment_id=installment.id, amount_paise=5_00_00_00,
                    channel=ReceiptChannel.UPI,
                ),
            )
            assert receipt.receipt_number == "RCPT-000043"

    def test_failed_posting_leaves_no_mutation(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            _tenant, admin, _project, lead = _fixture(session)
            installment = _booked_plan(session, admin, lead, 10_00_00_00)
            before = session.scalar(select(func.count()).select_from(Receipt))

            with pytest.raises(InstallmentNotFoundError):
                service.record_receipt(
                    session, actor=admin,
                    payload=ReceiptCreateRequest(
                        installment_id=UUID(int=0), amount_paise=1,
                        channel=ReceiptChannel.UPI,
                    ),
                )
            with pytest.raises(HTTPException):
                service.record_receipt(
                    session, actor=admin,
                    payload=ReceiptCreateRequest(
                        installment_id=installment.id, amount_paise=99_00_00_00,
                        channel=ReceiptChannel.UPI,
                    ),
                )
            session.expire_all()
            assert session.scalar(select(func.count()).select_from(Receipt)) == before


class TestTenantIsolation:
    def test_tenant_b_cannot_post_to_tenant_a_installment(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            _tenant_a, admin_a, _project_a, lead_a = _fixture(session, slug="fin-a")
            installment = _booked_plan(session, admin_a, lead_a, 10_00_00_00)
            _tenant_b, admin_b, _project_b, _lead_b = _fixture(session, slug="fin-b")

            with pytest.raises(InstallmentNotFoundError):
                service.record_receipt(
                    session, actor=admin_b,
                    payload=ReceiptCreateRequest(
                        installment_id=installment.id, amount_paise=1,
                        channel=ReceiptChannel.UPI,
                    ),
                )

    def test_receipt_numbers_are_scoped_per_tenant(
        self, test_session_factory: sessionmaker[Session]
    ) -> None:
        with test_session_factory() as session:
            tenant_a, admin_a, _pa, lead_a = _fixture(session, slug="fin-a")
            installment_a = _booked_plan(session, admin_a, lead_a, 10_00_00_00)
            tenant_b, admin_b, _pb, lead_b = _fixture(session, slug="fin-b")
            installment_b = _booked_plan(session, admin_b, lead_b, 10_00_00_00)

            receipt_a = service.record_receipt(
                session, actor=admin_a,
                payload=ReceiptCreateRequest(
                    installment_id=installment_a.id, amount_paise=1_00,
                    channel=ReceiptChannel.UPI,
                ),
            )
            receipt_b = service.record_receipt(
                session, actor=admin_b,
                payload=ReceiptCreateRequest(
                    installment_id=installment_b.id, amount_paise=1_00,
                    channel=ReceiptChannel.UPI,
                ),
            )
            # Each tenant's sequence is independent; both may hold the same number.
            assert receipt_a.receipt_number == receipt_b.receipt_number == "RCPT-000001"
            numbers_a = session.scalars(
                select(Receipt.receipt_number).where(Receipt.tenant_id == tenant_a.id)
            ).all()
            assert set(numbers_a) == {"RCPT-000001"}
