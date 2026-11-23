"""Collections command centre tests: calendar, reminders, promises, escalations, stats.

Covers:
- calendar: voided receipts excluded, overdue aging buckets, per-row detail.
- reminder sequencing: policy offsets, no duplicates per (installment, offset),
  dispatch-time consent suppression.
- payment promises: record-only; balances never change.
- escalations: age-threshold grouping by severity, read-only suggestions.
- analytics: recovered 30/90d, aging totals, reminder->payment counts.
- tenant isolation on every endpoint.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.security import hash_password
from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.messaging.dispatcher import process_due_deliveries
from app.modules.messaging.models import DeliveryStatus, MessageDelivery
from app.modules.postsales import service as postsales_service
from app.modules.postsales.models import Installment, InstallmentStatus, Receipt
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

from app.modules.collections import reminders, service
from app.modules.collections.models import CollectionReminder, InstallmentPromise
from app.modules.collections.policy import DEFAULT_OFFSETS, DEFAULT_ESCALATION_THRESHOLDS, resolve_policy
from app.modules.settings.models import SystemSetting


def _fixture(session: Session, *, slug: str = "cc-co"):
    tenant = Tenant(slug=slug, name=slug)
    session.add(tenant)
    session.flush()
    role = session.scalars(select(Role).where(Role.name == RoleName.ADMIN.value)).first()
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    admin = User(
        tenant_id=tenant.id, full_name="Admin", email=f"a@{slug}.example",
        password_hash=hash_password(TEST_PASSWORD), role_id=role.id, is_active=True,
    )
    session.add(admin)
    session.flush()
    project = Project(
        tenant_id=tenant.id, name="Tower", slug=f"tower-{slug}", location="Pune",
        status=ProjectStatus.ACTIVE.value, created_by=admin.id,
    )
    session.add(project)
    session.flush()
    lead = Lead(
        tenant_id=tenant.id, full_name="Buyer One", email=f"buyer@{slug}.example",
        phone="+919800000001", project_id=project.id, source=LeadSource.WEBSITE.value,
        status=LeadStatus.CONVERTED.value, consent_to_contact=True,
    )
    session.add(lead)
    session.commit()
    return tenant, admin, project, lead


def _booking_with_installments(
    session: Session, admin, lead, *, dues: list[tuple[str, int, date]]
):
    booking = postsales_service.create_booking(
        session,
        actor=admin,
        payload=SaleBookingCreateRequest(
            lead_id=lead.id, unit_number="A-101",
            consideration_paise=sum(amount for _, amount, _ in dues),
        ),
    )
    plan = postsales_service.create_plan(
        session,
        actor=admin,
        booking_id=booking.id,
        payload=PaymentPlanCreateRequest(
            name="CLP", plan_type="CONSTRUCTION_LINKED",
            installments=[
                InstallmentSpec(milestone=name, amount_paise=amount, due_on=due)
                for name, amount, due in dues
            ],
        ),
    )
    return booking, plan


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

def test_calendar_groups_by_day_and_excludes_voided_receipts(
    test_session_factory: sessionmaker[Session],
) -> None:
    today = date.today()
    month = f"{today.year:04d}-{today.month:02d}"
    with test_session_factory() as session:
        tenant, admin, project, lead = _fixture(session)
        booking, plan = _booking_with_installments(
            session, admin, lead,
            dues=[
                ("Booking", 10_000, today),
                ("Slab", 20_000, today + timedelta(days=3)),
            ],
        )
        # Live receipt 4000 against first installment + voided 6000 (excluded).
        live = postsales_service.record_receipt(
            session, actor=admin,
            payload=ReceiptCreateRequest(
                installment_id=plan.installments[0].id, amount_paise=4000, channel="UPI",
            ),
        )
        postsales_service.record_receipt(
            session, actor=admin,
            payload=ReceiptCreateRequest(
                installment_id=plan.installments[0].id, amount_paise=6000, channel="UPI",
            ),
        )
        # Void the second receipt so live paid = 4000.
        second = session.scalars(
            select(Receipt).where(Receipt.installment_id == plan.installments[0].id)
            .order_by(Receipt.paid_at)
        ).all()[1]
        second.voided_at = datetime.now(UTC)
        second.void_reason = "test reversal"
        session.commit()

        result = service.calendar(session, tenant_id=tenant.id, month=month)
        assert result["month"] == month
        flat = [row for day in result["days"] for row in day["rows"]]
        assert len(flat) == 2
        first = next(r for r in flat if r["milestone"] == "Booking")
        assert first["amount_paise"] == 10_000
        assert first["paid_paise"] == 4000  # voided 6000 excluded
        assert first["outstanding_paise"] == 6000
        assert first["customer_name"] == "Buyer One"
        assert first["project_id"] == project.id
        assert first["unit_number"] == "A-101"
        assert first["demand_letter_sent_at"] is None


def test_calendar_overdue_buckets(
    test_session_factory: sessionmaker[Session],
) -> None:
    today = date.today()
    month = f"{today.year:04d}-{today.month:02d}"
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session)
        _booking, plan = _booking_with_installments(
            session, admin, lead,
            dues=[
                ("old-91", 1000, today - timedelta(days=91)),
                ("old-45", 2000, today - timedelta(days=45)),
                ("old-10", 3000, today - timedelta(days=10)),
                ("future", 4000, today + timedelta(days=5)),
            ],
        )
        result = service.calendar(session, tenant_id=tenant.id, month=month)
        aging = result["overdue_aging"]
        assert aging["bucket_1_30_paise"] == 3000
        assert aging["bucket_31_60_paise"] == 2000
        assert aging["bucket_61_90_paise"] == 0
        assert aging["bucket_90_plus_paise"] == 1000


def test_calendar_project_filter(
    test_session_factory: sessionmaker[Session],
) -> None:
    today = date.today()
    month = f"{today.year:04d}-{today.month:02d}"
    with test_session_factory() as session:
        tenant, admin, project, lead = _fixture(session)
        _booking, _plan = _booking_with_installments(
            session, admin, lead, dues=[("due", 5000, today)],
        )
        other = uuid4()
        assert service.calendar(session, tenant_id=tenant.id, month=month, project_id=other)["days"] == []
        assert service.calendar(session, tenant_id=tenant.id, month=month, project_id=project.id)["days"]


# ---------------------------------------------------------------------------
# Reminder policy + sequencing
# ---------------------------------------------------------------------------

def test_policy_defaults_when_setting_missing(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, _admin, _project, _lead = _fixture(session)
        policy = resolve_policy(session, tenant_id=tenant.id)
        assert list(policy["offsets"]) == list(DEFAULT_OFFSETS)
        assert policy["escalation_thresholds"] == DEFAULT_ESCALATION_THRESHOLDS
        assert policy["channels"] == ["WHATSAPP", "SMS", "EMAIL"]


def test_policy_reads_tenant_override(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, _admin, _project, _lead = _fixture(session)
        session.add(SystemSetting(
            tenant_id=tenant.id, key="collections_reminder_policy",
            category="REMINDERS", value={
                "offsets": [-3, 0, 5],
                "escalation_thresholds": {"warning": 10, "critical": 40},
                "channels": ["EMAIL"],
            },
        ))
        session.commit()
        policy = resolve_policy(session, tenant_id=tenant.id)
        assert policy["offsets"] == [-3, 0, 5]
        assert policy["escalation_thresholds"] == {"warning": 10, "critical": 40, "severe": 90}
        assert policy["channels"] == ["EMAIL"]


def test_policy_invalid_offsets_fall_back(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, _admin, _project, _lead = _fixture(session)
        session.add(SystemSetting(
            tenant_id=tenant.id, key="collections_reminder_policy",
            category="REMINDERS", value={"offsets": ["not-an-int", 0]},
        ))
        session.commit()
        assert resolve_policy(session, tenant_id=tenant.id)["offsets"] == list(DEFAULT_OFFSETS)


def test_reminder_evaluation_queues_and_dedupes(
    test_session_factory: sessionmaker[Session],
) -> None:
    today = date.today()
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session)
        session.add(SystemSetting(
            tenant_id=tenant.id, key="collections_reminder_policy",
            category="REMINDERS", value={"offsets": [0, 7]},
        ))
        session.commit()
        _booking, plan = _booking_with_installments(
            session, admin, lead, dues=[("today", 5000, today)],
        )
        installment = plan.installments[0]

        first = reminders.queue_due_reminders(session, tenant_id=tenant.id, today=today)
        session.commit()
        assert first["queued"] >= 1  # offset 0 is due today
        rows = session.scalars(select(CollectionReminder)).all()
        offsets = {r.offset_key for r in rows}
        assert "0" in offsets

        # Re-running on the same day must not duplicate.
        second = reminders.queue_due_reminders(session, tenant_id=tenant.id, today=today)
        assert second["queued"] == 0
        assert second["skipped_existing"] >= 1

        # Installment paid in full before +7: no new reminders queued.
        postsales_service.record_receipt(
            session, actor=admin,
            payload=ReceiptCreateRequest(
                installment_id=installment.id, amount_paise=5000, channel="UPI",
            ),
        )
        later = reminders.queue_due_reminders(
            session, tenant_id=tenant.id, today=today + timedelta(days=7),
        )
        assert later["queued"] == 0


def test_reminder_concurrent_claim_skips_duplicate_installment(
    test_session_factory: sessionmaker[Session],
) -> None:
    """A pre-existing reminder row with the same (installment, offset) key
    must not abort the batch: the duplicate is skipped, siblings still queue."""
    today = date.today()
    with test_session_factory() as session:
        tenant, admin, project, lead = _fixture(session)
        session.add(SystemSetting(
            tenant_id=tenant.id, key="collections_reminder_policy",
            category="REMINDERS", value={"offsets": [0]},
        ))
        session.commit()
        _b1, plan1 = _booking_with_installments(
            session, admin, lead, dues=[("a", 1000, today)],
        )
        other_lead = Lead(
            tenant_id=tenant.id, full_name="Buyer Two", email="two2@cc-co.example",
            phone="+919800000009", project_id=project.id,
            source=LeadSource.WEBSITE.value, status=LeadStatus.CONVERTED.value,
            consent_to_contact=True,
        )
        session.add(other_lead)
        session.flush()
        _b2, plan2 = _booking_with_installments(
            session, admin, other_lead, dues=[("b", 2000, today)],
        )
        first_id = plan1.installments[0].id
        second_id = plan2.installments[0].id
        # A competing worker already queued the first installment's reminder.
        session.add(CollectionReminder(
            tenant_id=tenant.id, installment_id=first_id, offset_key="0",
            channel="WHATSAPP", scheduled_for=datetime.now(UTC),
            queued_at=datetime.now(UTC), created_at=datetime.now(UTC),
        ))
        session.commit()

        counts = reminders.queue_due_reminders(session, tenant_id=tenant.id, today=today)
        session.commit()
        # The duplicate is skipped, but the second installment still queues.
        assert counts["queued"] == 1
        assert counts["skipped_existing"] == 1
        queued = session.scalars(select(MessageDelivery)).all()
        assert len(queued) == 1
        assert queued[0].entity_id == second_id


def test_reminder_consent_suppression_at_dispatch(
    test_session_factory: sessionmaker[Session],
) -> None:
    today = date.today()
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session)
        session.add(SystemSetting(
            tenant_id=tenant.id, key="collections_reminder_policy",
            category="REMINDERS", value={"offsets": [0]},
        ))
        session.commit()
        _booking, plan = _booking_with_installments(
            session, admin, lead, dues=[("today", 5000, today)],
        )
        # Buyer opts out before dispatch.
        lead.opted_out = True
        lead.consent_to_contact = False
        session.commit()
        reminders.queue_due_reminders(session, tenant_id=tenant.id, today=today)
        session.commit()

        class _Provider:
            def __init__(self):
                self.sent = []
            def send(self, *, to, body, context):
                self.sent.append((to, body))
                return "ok"

        provider = _Provider()
        counts = process_due_deliveries(
            session, provider_factory=lambda name, settings: provider,
        )
        assert counts["suppressed"] >= 1
        assert provider.sent == []
        delivery = session.scalars(select(MessageDelivery)).one()
        assert delivery.status == DeliveryStatus.CANCELLED.value
        assert delivery.suppressed_reason == "RECIPIENT_OPTED_OUT"


# ---------------------------------------------------------------------------
# Payment promises
# ---------------------------------------------------------------------------

def test_promises_do_not_change_balances(
    test_session_factory: sessionmaker[Session],
) -> None:
    today = date.today()
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session)
        _booking, plan = _booking_with_installments(
            session, admin, lead, dues=[("due", 10_000, today)],
        )
        installment = plan.installments[0]
        from app.modules.postsales import repository as postsales_repo
        before = postsales_repo.receipt_total_for_installment(
            session, installment.id, tenant_id=tenant.id,
        )

        promise = service.create_promise(
            session, actor=admin, installment_id=installment.id,
            amount_paise=3000, promised_on=today + timedelta(days=2), note="Will pay",
        )
        session.commit()
        assert promise.id is not None
        after = postsales_repo.receipt_total_for_installment(
            session, installment.id, tenant_id=tenant.id,
        )
        assert before == after == 0
        # Installment status unchanged.
        session.refresh(installment)
        assert installment.status in {
            InstallmentStatus.PENDING.value, InstallmentStatus.DUE.value,
        }

        listed = service.list_promises(
            session, tenant_id=tenant.id, installment_id=installment.id,
        )
        assert len(listed) == 1
        assert listed[0].amount_paise == 3000


def test_overdue_promises_flagged_in_calendar(
    test_session_factory: sessionmaker[Session],
) -> None:
    today = date.today()
    month = f"{today.year:04d}-{today.month:02d}"
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session)
        _booking, plan = _booking_with_installments(
            session, admin, lead, dues=[("due", 8000, today)],
        )
        service.create_promise(
            session, actor=admin, installment_id=plan.installments[0].id,
            amount_paise=8000, promised_on=today - timedelta(days=1), note=None,
        )
        session.commit()
        result = service.calendar(session, tenant_id=tenant.id, month=month)
        flat = [row for day in result["days"] for row in day["rows"]]
        assert flat[0]["has_overdue_promise"] is True


def test_promise_cross_tenant_404(
    test_session_factory: sessionmaker[Session],
) -> None:
    today = date.today()
    with test_session_factory() as session:
        _t1, admin1, _p1, lead1 = _fixture(session, slug="alpha")
        _t2, admin2, _p2, _lead2 = _fixture(session, slug="beta")
        _booking, plan = _booking_with_installments(
            session, admin1, lead1, dues=[("due", 1000, today)],
        )
        from app.modules.postsales.exceptions import InstallmentNotFoundError
        import pytest
        with pytest.raises(InstallmentNotFoundError):
            service.create_promise(
                session, actor=admin2, installment_id=plan.installments[0].id,
                amount_paise=500, promised_on=today, note=None,
            )


# ---------------------------------------------------------------------------
# Escalations
# ---------------------------------------------------------------------------

def test_escalations_grouped_by_severity(
    test_session_factory: sessionmaker[Session],
) -> None:
    today = date.today()
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session)
        session.add(SystemSetting(
            tenant_id=tenant.id, key="collections_reminder_policy",
            category="REMINDERS", value={
                "escalation_thresholds": {"warning": 10, "critical": 40},
            },
        ))
        session.commit()
        _booking, _plan = _booking_with_installments(
            session, admin, lead,
            dues=[
                ("warn", 1000, today - timedelta(days=20)),
                ("crit", 2000, today - timedelta(days=50)),
                ("fine", 3000, today + timedelta(days=5)),
            ],
        )
        # A second booking (different lead) in the warning band only.
        other_lead = Lead(
            tenant_id=tenant.id, full_name="Buyer Two", email="two@cc-co.example",
            phone="+919800000002", project_id=_project.id,
            source=LeadSource.WEBSITE.value, status=LeadStatus.CONVERTED.value,
            consent_to_contact=True,
        )
        session.add(other_lead)
        session.flush()
        _booking2, _plan2 = _booking_with_installments(
            session, admin, other_lead,
            dues=[("warn-only", 4000, today - timedelta(days=15))],
        )
        result = service.escalations(session, tenant_id=tenant.id, today=today)
        assert result["thresholds"] == {"warning": 10, "critical": 40, "severe": 90}
        crit_rows = result["groups"]["critical"]
        warn_rows = result["groups"]["warning"]
        # First booking crosses critical (50d) and is grouped by its worst band.
        assert len(crit_rows) == 1 and crit_rows[0]["suggested_action"]
        assert crit_rows[0]["overdue_installments"] == 2
        assert len(warn_rows) == 1
        # Read-only: no cancellation/status flip was applied.
        rows = session.scalars(select(Installment)).all()
        assert all(r.status in {
            InstallmentStatus.PENDING.value, InstallmentStatus.OVERDUE.value,
            InstallmentStatus.DUE.value,
        } for r in rows)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_stats_math_and_conversion_counts(
    test_session_factory: sessionmaker[Session],
) -> None:
    now = datetime.now(UTC)
    today = now.date()
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session)
        _booking, plan = _booking_with_installments(
            session, admin, lead, dues=[("old", 10_000, today - timedelta(days=10))],
        )
        installment = plan.installments[0]
        # Receipt 20 days ago (within 30d and 90d).
        r1 = postsales_service.record_receipt(
            session, actor=admin,
            payload=ReceiptCreateRequest(
                installment_id=installment.id, amount_paise=4000, channel="UPI",
                paid_at=now - timedelta(days=20),
            ),
        )
        # Receipt 100 days ago (only outside both windows).
        installment.amount_paise = 20_000
        session.flush()
        postsales_service.record_receipt(
            session, actor=admin,
            payload=ReceiptCreateRequest(
                installment_id=installment.id, amount_paise=6000, channel="UPI",
                paid_at=now - timedelta(days=100),
            ),
        )
        # Voided receipt (must not count in recovered).
        voided = postsales_service.record_receipt(
            session, actor=admin,
            payload=ReceiptCreateRequest(
                installment_id=installment.id, amount_paise=2000, channel="UPI",
                paid_at=now - timedelta(days=5),
            ),
        )
        voided.voided_at = now
        voided.void_reason = "test"
        session.flush()
        # A reminder row exists for this installment.
        session.add(CollectionReminder(
            tenant_id=tenant.id, installment_id=installment.id, offset_key="0",
            channel="WHATSAPP", queued_at=now - timedelta(days=21),
            scheduled_for=now - timedelta(days=21),
        ))
        session.commit()

        stats = service.stats(session, tenant_id=tenant.id, now=now)
        assert stats["recovered_30d_paise"] == 4000
        assert stats["recovered_90d_paise"] == 4000
        assert stats["outstanding_paise"] == 20_000 - 10_000  # amount - live paid
        # Conversion counts: 1 reminder, 1 receipt within 30d after a reminder.
        conv = stats["reminder_payment_counts"]
        assert conv["reminders_queued"] == 1
        assert conv["payments_after_reminder"] >= 1


def test_tenant_isolation_calendar_and_stats(
    test_session_factory: sessionmaker[Session],
) -> None:
    today = date.today()
    month = f"{today.year:04d}-{today.month:02d}"
    with test_session_factory() as session:
        _t1, admin1, _p1, lead1 = _fixture(session, slug="iso-a")
        t2, _admin2, _p2, _lead2 = _fixture(session, slug="iso-b")
        _booking, _plan = _booking_with_installments(
            session, admin1, lead1, dues=[("due", 7000, today)],
        )
        result = service.calendar(session, tenant_id=t2.id, month=month)
        assert result["days"] == []
        stats = service.stats(session, tenant_id=t2.id)
        assert stats["outstanding_paise"] == 0
        assert stats["recovered_30d_paise"] == 0


# ---------------------------------------------------------------------------
# Regression tests for code-review findings (commit 25cf795)
# ---------------------------------------------------------------------------

def test_waived_installment_never_queues_reminder(
    test_session_factory: sessionmaker[Session],
) -> None:
    """HIGH: WAIVED installments must not queue payment demands even though
    their live receipts are below the amount (a write-off, not an arrears)."""
    today = date.today()
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session)
        session.add(SystemSetting(
            tenant_id=tenant.id, key="collections_reminder_policy",
            category="REMINDERS", value={"offsets": [0]},
        ))
        session.commit()
        _booking, plan = _booking_with_installments(
            session, admin, lead, dues=[("waived", 5000, today)],
        )
        installment = plan.installments[0]
        installment.status = InstallmentStatus.WAIVED.value
        session.commit()
        counts = reminders.queue_due_reminders(session, tenant_id=tenant.id, today=today)
        session.commit()
        assert counts["queued"] == 0
        assert counts["skipped_settled"] == 1
        assert session.scalars(select(MessageDelivery)).all() == []


def test_escalation_totals_include_subthreshold_overdue_installments(
    test_session_factory: sessionmaker[Session],
) -> None:
    """MEDIUM: an account crossing the warning band must still count its
    newer, below-threshold overdue installments in outstanding_paise and
    overdue_installments (not just the threshold-crossing row)."""
    today = date.today()
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session)
        session.add(SystemSetting(
            tenant_id=tenant.id, key="collections_reminder_policy",
            category="REMINDERS", value={
                "escalation_thresholds": {"warning": 30, "critical": 60, "severe": 90},
            },
        ))
        session.commit()
        _booking, _plan = _booking_with_installments(
            session, admin, lead,
            dues=[
                ("old-crosses", 1000, today - timedelta(days=45)),  # > warning 30
                ("new-below", 7000, today - timedelta(days=5)),      # < warning 30
            ],
        )
        result = service.escalations(session, tenant_id=tenant.id, today=today)
        rows = result["groups"]["warning"]
        assert len(rows) == 1
        # Both overdue installments are counted: 1000 + 7000 outstanding.
        assert rows[0]["outstanding_paise"] == 8000
        assert rows[0]["overdue_installments"] == 2
        assert rows[0]["days_overdue"] == 45


def test_overdue_promise_fulfilled_by_payment_after_promise(
    test_session_factory: sessionmaker[Session],
) -> None:
    """HIGH: a promise for the remaining balance on a part-paid installment
    is fulfilled once the buyer pays the promised amount AFTER the promise —
    it must not stay overdue just because lifetime receipts < promise amount."""
    now = datetime.now(UTC)
    today = now.date()
    month = f"{today.year:04d}-{today.month:02d}"
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session)
        _booking, plan = _booking_with_installments(
            session, admin, lead, dues=[("due", 10_000, today)],
        )
        installment = plan.installments[0]
        # Buyer already paid 4000 before promising the remaining 6000.
        postsales_service.record_receipt(
            session, actor=admin,
            payload=ReceiptCreateRequest(
                installment_id=installment.id, amount_paise=4000, channel="UPI",
                paid_at=now - timedelta(days=10),
            ),
        )
        service.create_promise(
            session, actor=admin, installment_id=installment.id,
            amount_paise=6000, promised_on=today - timedelta(days=2), note="rest",
        )
        session.commit()
        # Buyer pays the promised 6000 remainder after the promise was recorded.
        # Use a fresh timestamp taken AFTER the promise row's created_at so the
        # payment falls inside the post-promise fulfillment window; promised_on
        # is already in the past, so only fulfillment is in question.
        postsales_service.record_receipt(
            session, actor=admin,
            payload=ReceiptCreateRequest(
                installment_id=installment.id, amount_paise=6000, channel="UPI",
                paid_at=datetime.now(UTC),
            ),
        )
        session.commit()
        result = service.calendar(session, tenant_id=tenant.id, month=month)
        flat = [row for day in result["days"] for row in day["rows"]]
        # Promise is fulfilled -> not flagged overdue.
        assert flat[0]["has_overdue_promise"] is False


def test_scheduler_failed_tenant_day_not_marked_evaluated() -> None:
    """MEDIUM: a UTC day with a failed tenant must stay open for retry."""
    from app.modules.collections.scheduler import CollectionsReminderScheduler

    sched = CollectionsReminderScheduler()
    # Simulate a pass that returned a failed tenant.
    import app.modules.collections.scheduler as sched_mod

    class _FakeSession:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    calls = {"n": 0}

    def fake_queue_all(session, *, today=None):
        calls["n"] += 1
        return {"queued": 0, "failed_tenants": 1}

    orig_queue = sched_mod.queue_all_tenants
    orig_session = sched_mod.SessionLocal
    try:
        sched_mod.queue_all_tenants = fake_queue_all
        sched_mod.SessionLocal = lambda: _FakeSession()
        sched._run_sync_check()
        # Day not marked evaluated because a tenant failed -> retried next tick.
        assert sched._last_evaluated is None
        # Now all tenants succeed.
        sched_mod.queue_all_tenants = lambda s, *, today=None: {"queued": 0, "failed_tenants": 0}
        sched._run_sync_check()
        assert sched._last_evaluated is not None
    finally:
        sched_mod.queue_all_tenants = orig_queue
        sched_mod.SessionLocal = orig_session
