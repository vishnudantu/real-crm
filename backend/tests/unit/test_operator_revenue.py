"""Operator Revenue Command Centre tests: MRR/ARR math, failures, expansion,
renewals, and revenue.read gating (OWNER included; SUPPORT excluded)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.security import hash_password
from app.modules.billing.models import (
    BillingWebhookEvent,
    Invoice,
    Subscription,
    SubscriptionStatus,
)
from app.modules.leads.models import Lead, LeadSource
from app.modules.operator import revenue
from app.modules.operator.models import OperatorPermission, OperatorUser
from app.modules.operator.security import create_operator_token
from app.modules.plans.models import Plan
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD


def _operator(session: Session, *, role: str = "OWNER") -> OperatorUser:
    row = OperatorUser(
        email=f"op-{uuid4().hex[:8]}@propflow.example",
        full_name="Owner",
        password_hash=hash_password(TEST_PASSWORD),
        role=role,
        permissions=[],
    )
    session.add(row)
    session.flush()
    return row


def _plan(session: Session, *, price_paise: int = 49_900) -> Plan:
    row = Plan(
        code=f"plan-{uuid4().hex[:8]}", name="Growth", price_paise=price_paise,
        max_users=5, leads_per_month=10, whatsapp_msgs_per_month=100,
    )
    session.add(row)
    session.flush()
    return row


def _tenant(session: Session, *, name: str | None = None) -> Tenant:
    row = Tenant(slug=f"t-{uuid4().hex[:8]}", name=name or "Acme Realty")
    session.add(row)
    session.flush()
    return row


def _subscription(
    session: Session, tenant: Tenant, plan: Plan, *, status_value: str,
    created_at: datetime | None = None,
    period_end: datetime | None = None,
) -> Subscription:
    row = Subscription(
        tenant_id=tenant.id, plan_id=plan.id, status=status_value,
        current_period_start=(created_at or datetime.now(UTC)) - timedelta(days=15),
        current_period_end=period_end,
        created_at=created_at or datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def _invoice(session: Session, tenant: Tenant, subscription: Subscription, *, amount_paise: int, paid_at: datetime, status_value: str = "paid") -> None:
    session.add(
        Invoice(
            tenant_id=tenant.id, subscription_id=subscription.id,
            razorpay_invoice_id=f"inv-{uuid4().hex[:10]}", amount_paise=amount_paise,
            status=status_value, paid_at=paid_at,
        )
    )
    session.flush()


def _user(session: Session, tenant: Tenant) -> User:
    role = session.scalar(
        __import__("sqlalchemy").select(Role).where(Role.name == RoleName.ADMIN.value)
    )
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    user = User(
        tenant_id=tenant.id, full_name="Tenant Admin",
        email=f"a-{uuid4().hex[:8]}@acme.example",
        password_hash=hash_password(TEST_PASSWORD), role_id=role.id, is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def test_recurring_revenue_uses_latest_subscription_per_tenant(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        plan = _plan(session, price_paise=50_000)
        plan_b = _plan(session, price_paise=99_000)
        tenant_a = _tenant(session, name="A")
        tenant_b = _tenant(session, name="B")
        tenant_c = _tenant(session, name="C")

        # A: old cancelled ₹50k replaced by ACTIVE ₹99k → only the latest counts.
        _subscription(session, tenant_a, plan, status_value=SubscriptionStatus.CANCELLED.value,
                      created_at=datetime.now(UTC) - timedelta(days=90))
        _subscription(session, tenant_a, plan_b, status_value=SubscriptionStatus.ACTIVE.value,
                      created_at=datetime.now(UTC) - timedelta(days=1))
        # B: latest is HALTED → no MRR, reported at risk.
        _subscription(session, tenant_b, plan, status_value=SubscriptionStatus.HALTED.value)
        # C: ACTIVE ₹50k.
        _subscription(session, tenant_c, plan, status_value=SubscriptionStatus.ACTIVE.value)

        result = revenue.recurring_revenue(session)
        assert result["mrr_paise"] == 149_000
        assert result["arr_paise"] == 149_000 * 12
        assert result["active_subscriptions"] == 2
        assert result["at_risk"]["halted_count"] == 1
        assert result["at_risk"]["halted_mrr_paise"] == 50_000
        assert result["at_risk"]["past_due_count"] == 0


def test_invoiced_trend_and_payment_failures(
    test_session_factory: sessionmaker[Session],
) -> None:
    this_first = datetime.now(UTC).date().replace(day=1)
    prev_end = this_first - timedelta(days=1)
    prev_first = prev_end.replace(day=1)

    with test_session_factory() as session:
        plan = _plan(session)
        tenant = _tenant(session)
        sub = _subscription(session, tenant, plan, status_value=SubscriptionStatus.ACTIVE.value)
        _invoice(session, tenant, sub, amount_paise=1_000, paid_at=datetime(prev_first.year, prev_first.month, 5, tzinfo=UTC))
        _invoice(session, tenant, sub, amount_paise=2_000, paid_at=datetime(this_first.year, this_first.month, 5, tzinfo=UTC))
        # Draft invoices and non-paid statuses never appear in invoiced revenue.
        _invoice(session, tenant, sub, amount_paise=99_000, paid_at=datetime(this_first.year, this_first.month, 6, tzinfo=UTC), status_value="draft")

        session.add(
            BillingWebhookEvent(
                provider="razorpay", event_id=f"evt-{uuid4().hex[:8]}",
                event_type="payment.failed", payload={},
            )
        )
        session.add(
            BillingWebhookEvent(
                provider="razorpay", event_id=f"evt-{uuid4().hex[:8]}",
                event_type="subscription.activated", payload={},
            )
        )
        session.commit()

        months = revenue.invoiced_by_month(session, months=3)
        by_month = {point["month"]: point for point in months}
        assert by_month[prev_first]["invoiced_paise"] == 1_000
        assert by_month[this_first]["invoiced_paise"] == 2_000
        assert by_month[this_first]["invoice_count"] == 1

        failures = revenue.payment_failures(session, since=datetime.now(UTC) - timedelta(days=30))
        assert failures["count_last_30_days"] == 1


def test_expansion_signals_and_renewals(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        plan = _plan(session)  # leads limit 10, users limit 5
        hot = _tenant(session, name="Hot Tenant")
        cool = _tenant(session, name="Cool Tenant")
        _subscription(session, hot, plan, status_value=SubscriptionStatus.ACTIVE.value,
                      period_end=datetime.now(UTC) + timedelta(days=10))
        _subscription(session, cool, plan, status_value=SubscriptionStatus.ACTIVE.value,
                      period_end=datetime.now(UTC) + timedelta(days=200))

        admin = _user(session, hot)
        project = Project(
            tenant_id=hot.id, name="Skyline", slug=f"sky-{uuid4().hex[:6]}",
            location="Pune", status=ProjectStatus.ACTIVE.value, created_by=admin.id,
        )
        session.add(project)
        session.flush()
        # 9 of 10 monthly leads ⇒ 90% ≥ 80% expansion threshold.
        for _ in range(9):
            session.add(
                Lead(
                    tenant_id=hot.id, full_name="Buyer", email=f"{uuid4().hex[:8]}@x.example",
                    project_id=project.id, source=LeadSource.WEBSITE.value, status="NEW",
                    created_at=datetime.now(UTC),
                )
            )
        session.commit()

        signals = revenue.expansion_signals(session)
        lead_signal = next(s for s in signals if s["tenant_id"] == hot.id and s["meter"] == "leads")
        assert lead_signal["used"] == 9
        assert lead_signal["limit"] == 10
        assert lead_signal["ratio"] == 0.9
        assert all(s["tenant_id"] != cool.id for s in signals)

        renewals = revenue.renewals_due(session, within_days=30)
        assert renewals["count"] == 1
        assert renewals["subscriptions"][0]["tenant_id"] == hot.id
        assert renewals["subscriptions"][0]["price_paise"] == 49_900
        assert renewals["mrr_at_stake_paise"] == 49_900


@pytest.fixture()
def client_with_db(client, override_db):
    return client


def test_revenue_route_owner_allowed_support_forbidden(
    client_with_db, test_session_factory, test_settings
) -> None:
    with test_session_factory() as session:
        owner = _operator(session, role="OWNER")
        support = _operator(session, role="SUPPORT")
        session.commit()
        owner_headers = {"Authorization": f"Bearer {create_operator_token(owner, settings=test_settings)}"}
        support_headers = {"Authorization": f"Bearer {create_operator_token(support, settings=test_settings)}"}

    anon = client_with_db.get("/api/v1/operator/revenue/summary")
    assert anon.status_code == 401

    forbidden = client_with_db.get("/api/v1/operator/revenue/summary", headers=support_headers)
    assert forbidden.status_code == 403

    allowed = client_with_db.get("/api/v1/operator/revenue/summary", headers=owner_headers)
    assert allowed.status_code == 200, allowed.text
    body = allowed.json()
    assert body["mrr_paise"] == 0
    assert body["arr_paise"] == 0
    assert len(body["invoiced"]) == 6
    assert body["renewals"]["window_days"] == 30
    assert body["failures"]["count_last_30_days"] == 0


def test_revenue_permission_grant_for_sales_operator(
    client_with_db, test_session_factory, test_settings
) -> None:
    """An explicit revenue.read grant on a non-OWNER operator opens the view."""

    with test_session_factory() as session:
        sales = _operator(session, role="SALES")
        sales.permissions = [OperatorPermission.REVENUE_READ.value]
        session.commit()
        headers = {"Authorization": f"Bearer {create_operator_token(sales, settings=test_settings)}"}

    allowed = client_with_db.get("/api/v1/operator/revenue/summary", headers=headers)
    assert allowed.status_code == 200, allowed.text
