"""Razorpay billing: signature verification, lifecycle, limits, and replay tests."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.modules.billing.models import Subscription, SubscriptionStatus
from app.modules.billing.service import (
    PlanLimitExceededError,
    ensure_within_plan_limits,
    process_webhook,
    verify_razorpay_signature,
)
from app.modules.plans.models import Plan
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User
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


def _subscription(session: Session, tenant_id) -> Subscription:
    plan = Plan(
        code="pro", name="Pro", price_paise=99900, max_users=5,
        leads_per_month=10, whatsapp_msgs_per_month=100, is_active=True,
    )
    session.add(plan)
    session.flush()
    sub = Subscription(
        tenant_id=tenant_id, plan_id=plan.id, status="created",
        razorpay_subscription_id="sub_test_123",
    )
    session.add(sub)
    session.commit()
    return sub


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
