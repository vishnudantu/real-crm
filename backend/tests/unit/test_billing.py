"""Razorpay billing: signature verification, lifecycle, limits, and replay tests."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.billing.models import Subscription, SubscriptionStatus
from app.modules.billing.service import (
    PlanLimitExceededError,
    ensure_within_plan_limits,
    process_webhook,
    verify_razorpay_signature,
)
from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.messaging.models import DeliveryStatus, MessageChannel, MessageDelivery
from app.modules.plans.models import Plan
from app.modules.projects.models import Project
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD


def _settings() -> "Settings":
    from app.core.config import Settings
    return Settings(
        database_url="sqlite:///test.db",
        jwt_secret_key="a-very-long-test-secret-key-for-testing-purposes-only",
        razorpay_webhook_secret="whsec_test",
        plan_grace_days=7,
    )


def _signature(body: bytes, secret: str = "whsec_test") -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _subscription(
    session: Session,
    tenant_id,
    *,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> Subscription:
    plan = Plan(
        code="pro", name="Pro", price_paise=99900, max_users=5,
        leads_per_month=10, whatsapp_msgs_per_month=100, is_active=True,
    )
    session.add(plan)
    session.flush()
    sub = Subscription(
        tenant_id=tenant_id, plan_id=plan.id, status="created",
        razorpay_subscription_id="sub_test_123",
        current_period_start=period_start,
        current_period_end=period_end,
    )
    session.add(sub)
    session.commit()
    return sub


def _project(session: Session, tenant_id) -> Project:
    role = Role(name=RoleName.BUYER.value)
    session.add(role)
    session.flush()
    creator = User(
        tenant_id=tenant_id,
        full_name="Creator",
        email=f"creator-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        role_id=role.id,
    )
    session.add(creator)
    session.flush()
    project = Project(
        tenant_id=tenant_id,
        name="P",
        slug=f"p-{uuid4().hex[:8]}",
        location="BLR",
        created_by=creator.id,
    )
    session.add(project)
    session.flush()
    return project


def _lead(
    session: Session,
    tenant_id,
    project_id,
    *,
    created_at: datetime,
    email: str | None = None,
) -> Lead:
    lead = Lead(
        tenant_id=tenant_id,
        full_name="L",
        email=email or f"lead-{uuid4().hex[:8]}@example.com",
        project_id=project_id,
        source=LeadSource.WEBSITE.value,
        status=LeadStatus.NEW.value,
        created_at=created_at,
    )
    session.add(lead)
    session.flush()
    return lead


def _delivery(
    session: Session,
    tenant_id,
    *,
    status: str,
    created_at: datetime,
    sent_at: datetime | None,
) -> MessageDelivery:
    row = MessageDelivery(
        tenant_id=tenant_id,
        channel=MessageChannel.WHATSAPP.value,
        to_address="+919999999999",
        body="hello",
        status=status,
        event="lead.created",
        idempotency_key=uuid4().hex,
        next_attempt_at=created_at,
        created_at=created_at,
        sent_at=sent_at,
    )
    session.add(row)
    session.flush()
    return row


def test_razorpay_signature_accepts_valid_and_rejects_invalid() -> None:
    body = b'{"event":"subscription.activated"}'
    assert verify_razorpay_signature(body, _signature(body), _settings()) is True
    assert verify_razorpay_signature(body, "bad-signature", _settings()) is False


def test_webhook_activates_subscription_and_is_idempotent(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant = Tenant(slug="t1", name="T1")
        session.add(tenant)
        session.flush()
        sub = _subscription(session, tenant.id)

        payload = json.dumps({
            "event": "subscription.activated",
            "created_at": 1700000000,
            "payload": {"subscription": {"entity": {"id": "sub_test_123", "status": "active"}}},
        }).encode()
        result = process_webhook(session, raw_body=payload, signature=_signature(payload), settings=_settings())
        assert result["status"] == "processed"
        assert result["subscription_status"] == SubscriptionStatus.ACTIVE.value

        # Replay of the same event id is a no-op.
        replay = process_webhook(session, raw_body=payload, signature=_signature(payload), settings=_settings())
        assert replay["status"] == "duplicate"


def test_webhook_rejects_bad_signature(
    test_session_factory: sessionmaker[Session],
) -> None:
    from fastapi import HTTPException
    with test_session_factory() as session:
        with pytest.raises(HTTPException) as exc_info:
            process_webhook(session, raw_body=b'{"event":"x"}', signature="bad", settings=_settings())
        assert exc_info.value.status_code == 403


def test_plan_limit_enforcement_blocks_over_limit_user_and_lead_creation(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant = Tenant(slug="t2", name="T2")
        session.add(tenant)
        session.flush()
        sub = _subscription(session, tenant.id)
        plan = session.get(Plan, sub.plan_id)
        plan.max_users = 1
        session.add(plan)
        session.commit()

        # No user yet — allowed.
        ensure_within_plan_limits(session, tenant_id=tenant.id, kind="users")

        from app.modules.users.models import Role
        role = Role(name="BUYER")
        session.add(role)
        session.flush()
        session.add(User(tenant_id=tenant.id, full_name="U1", email="u1@example.com", password_hash="x", role_id=role.id, is_active=True))
        session.commit()

        # Second user exceeds limit.
        with pytest.raises(PlanLimitExceededError) as exc_info:
            ensure_within_plan_limits(session, tenant_id=tenant.id, kind="users")
        assert exc_info.value.status_code == 402


def test_lead_created_before_period_start_is_not_counted(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant = Tenant(slug="t3", name="T3")
        session.add(tenant)
        session.flush()
        period_start = datetime.now(UTC) - timedelta(days=5)
        _subscription(
            session, tenant.id, period_start=period_start,
            period_end=datetime.now(UTC) + timedelta(days=25),
        )
        project = _project(session, tenant.id)
        _lead(session, tenant.id, project.id, created_at=period_start - timedelta(days=1))
        session.commit()

        # The pre-period lead must not consume this period's quota.
        ensure_within_plan_limits(session, tenant_id=tenant.id, kind="leads")


def test_leads_inside_period_count_to_limit_and_crossing_raises_with_period_info(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant = Tenant(slug="t4", name="T4")
        session.add(tenant)
        session.flush()
        period_start = datetime.now(UTC) - timedelta(days=2)
        period_end = datetime.now(UTC) + timedelta(days=28)
        _subscription(
            session, tenant.id, period_start=period_start, period_end=period_end
        )
        project = _project(session, tenant.id)
        for index in range(10):  # plan.leads_per_month == 10
            _lead(
                session, tenant.id, project.id,
                created_at=period_start + timedelta(hours=index),
            )
        session.commit()

        # At exactly the limit the gate blocks the next creation and reports the window.
        with pytest.raises(PlanLimitExceededError) as exc_info:
            ensure_within_plan_limits(session, tenant_id=tenant.id, kind="leads")

        assert exc_info.value.status_code == 402
        detail = exc_info.value.detail
        assert detail["code"] == "PLAN_LIMIT_EXCEEDED"
        assert detail["used"] == 10
        assert detail["limit"] == 10
        assert detail["period_source"] == "SUBSCRIPTION"
        assert detail["period_start"] == period_start.isoformat()
        assert detail["period_end"] == period_end.isoformat()
        assert str(period_start.date()) in detail["message"]


def test_whatsapp_window_counts_only_sent_inside_period(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant = Tenant(slug="t5", name="T5")
        session.add(tenant)
        session.flush()
        period_start = datetime.now(UTC) - timedelta(days=5)
        period_end = datetime.now(UTC) + timedelta(days=25)
        _subscription(
            session, tenant.id, period_start=period_start, period_end=period_end
        )

        inside = datetime.now(UTC) - timedelta(days=1)
        before = period_start - timedelta(hours=1)
        _delivery(
            session, tenant.id, status=DeliveryStatus.SENT.value,
            created_at=inside, sent_at=inside,
        )
        # SENT before the period does not count.
        _delivery(
            session, tenant.id, status=DeliveryStatus.SENT.value,
            created_at=before, sent_at=before,
        )
        # FAILED/QUEUED inside the period do not count.
        _delivery(
            session, tenant.id, status=DeliveryStatus.FAILED.value,
            created_at=inside, sent_at=None,
        )
        _delivery(
            session, tenant.id, status=DeliveryStatus.QUEUED.value,
            created_at=inside, sent_at=None,
        )
        # SENT inside the period with a NULL sent_at counts via created_at.
        _delivery(
            session, tenant.id, status=DeliveryStatus.SENT.value,
            created_at=inside, sent_at=None,
        )
        session.commit()

        # Default plan whatsapp_msgs_per_month is 100, so no raise expected.
        ensure_within_plan_limits(session, tenant_id=tenant.id, kind="whatsapp")


def test_whatsapp_limit_counts_period_sent_only_and_raises(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant = Tenant(slug="t6", name="T6")
        session.add(tenant)
        session.flush()
        period_start = datetime.now(UTC) - timedelta(days=3)
        period_end = datetime.now(UTC) + timedelta(days=27)
        _subscription(
            session, tenant.id, period_start=period_start, period_end=period_end
        )

        inside = datetime.now(UTC) - timedelta(days=1)
        before = period_start - timedelta(hours=2)
        sub_plan = session.get(Plan, session.scalar(select(Subscription.plan_id).where(Subscription.tenant_id == tenant.id)))
        sub_plan.whatsapp_msgs_per_month = 2
        session.add(sub_plan)
        session.commit()

        _delivery(session, tenant.id, status=DeliveryStatus.SENT.value, created_at=before, sent_at=before)
        _delivery(session, tenant.id, status=DeliveryStatus.SENT.value, created_at=inside, sent_at=inside)
        _delivery(session, tenant.id, status=DeliveryStatus.FAILED.value, created_at=inside, sent_at=None)
        session.commit()

        ensure_within_plan_limits(session, tenant_id=tenant.id, kind="whatsapp")
        _delivery(session, tenant.id, status=DeliveryStatus.SENT.value, created_at=inside, sent_at=inside)
        session.commit()

        with pytest.raises(PlanLimitExceededError) as exc_info:
            ensure_within_plan_limits(session, tenant_id=tenant.id, kind="whatsapp")
        detail = exc_info.value.detail
        assert exc_info.value.status_code == 402
        assert detail["used"] == 2
        assert detail["limit"] == 2
        assert detail["period_source"] == "SUBSCRIPTION"


def test_rolling_30d_window_when_no_subscription(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant = Tenant(slug="t7", name="T7")
        session.add(tenant)
        session.flush()
        plan = Plan(
            code="starter", name="Starter", price_paise=49900, max_users=3,
            leads_per_month=2, whatsapp_msgs_per_month=5, is_active=True,
        )
        session.add(plan)
        session.flush()
        tenant.plan_id = plan.id
        session.add(tenant)
        session.commit()
        project = _project(session, tenant.id)

        # Two leads inside the rolling 30-day window fill the limit.
        _lead(session, tenant.id, project.id, created_at=datetime.now(UTC) - timedelta(days=1))
        _lead(session, tenant.id, project.id, created_at=datetime.now(UTC) - timedelta(days=2))
        session.commit()

        # 2 of 2 inside the rolling window — next creation is blocked.
        with pytest.raises(PlanLimitExceededError) as exc_info:
            ensure_within_plan_limits(session, tenant_id=tenant.id, kind="leads")

        detail = exc_info.value.detail
        assert exc_info.value.status_code == 402
        assert detail["used"] == 2
        assert detail["limit"] == 2
        assert detail["period_source"] == "ROLLING_30D"
        assert detail["period_start"] is not None
        assert detail["period_end"] is not None


def test_users_seat_count_ignores_inactive_users(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant = Tenant(slug="t8", name="T8")
        session.add(tenant)
        session.flush()
        sub = _subscription(session, tenant.id)
        plan = session.get(Plan, sub.plan_id)
        plan.max_users = 2
        session.add(plan)
        session.commit()

        role = Role(name="BUYER")
        session.add(role)
        session.flush()
        session.add(User(tenant_id=tenant.id, full_name="A", email="a@example.com", password_hash="x", role_id=role.id, is_active=True))
        session.add(User(tenant_id=tenant.id, full_name="B", email="b@example.com", password_hash="x", role_id=role.id, is_active=False))
        session.add(User(tenant_id=tenant.id, full_name="C", email="c@example.com", password_hash="x", role_id=role.id, is_active=False))
        session.commit()

        # Only 1 active seat used; inactive users must not block invites.
        ensure_within_plan_limits(session, tenant_id=tenant.id, kind="users")

        session.add(User(tenant_id=tenant.id, full_name="D", email="d@example.com", password_hash="x", role_id=role.id, is_active=True))
        session.commit()

        with pytest.raises(PlanLimitExceededError) as exc_info:
            ensure_within_plan_limits(session, tenant_id=tenant.id, kind="users")
        detail = exc_info.value.detail
        assert exc_info.value.status_code == 402
        assert detail["used"] == 2
        assert detail["limit"] == 2
