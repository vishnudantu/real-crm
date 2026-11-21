"""Unit tests for the messaging engine, outbox dispatcher, and template rendering."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.modules.messaging.dispatcher import process_due_deliveries
from app.modules.messaging.engine import emit_event, render_template
from app.modules.messaging.models import (
    DeliveryStatus,
    MessageDelivery,
    MessageTemplate,
    TriggerRule,
)
from app.modules.messaging.providers.log_provider import LogProvider
from app.modules.tenancy.models import Tenant
from app.modules.users.models import RoleName, User


class _RecordingProvider:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[tuple[str, str]] = []

    def send(self, *, to: str, body: str, context: dict) -> str:
        if self.fail:
            raise RuntimeError("simulated provider outage")
        self.sent.append((to, body))
        return f"fake-{len(self.sent)}"


def test_render_replaces_merge_tags_and_preserves_unknown_tags() -> None:
    assert render_template("Hi {first_name}!", {"first_name": "Asha"}) == "Hi Asha!"
    assert render_template("No {unknown} tag", {}) == "No {unknown} tag"
    assert render_template("{{escaped}}", {}) == "{escaped}"


def _tenant_and_user(session: Session) -> tuple[Tenant, User]:
    tenant = Tenant(slug=f"t-{uuid4().hex[:8]}", name="Test Tenant")
    session.add(tenant)
    session.flush()
    role = next(iter(session.query(__import__('app.modules.users.models', fromlist=['Role']).Role).all()), None)
    if role is None:
        from app.modules.users.models import Role
        role = Role(name="BUYER")
        session.add(role)
        session.flush()
    user = User(
        tenant_id=tenant.id,
        full_name="Test User",
        email=f"u-{uuid4().hex[:8]}@example.com",
        password_hash="not-a-real-hash",
        role_id=role.id,
        is_active=True,
    )
    session.add(user)
    session.flush()
    return tenant, user


def _rule_and_template(session: Session, tenant_id, *, delay_minutes: int = 0) -> TriggerRule:
    template = MessageTemplate(
        tenant_id=tenant_id, name="Lead Welcome", channel="WHATSAPP", language="en",
        body="Hi {first_name}, thanks for your interest in {project_name}.",
        is_active=True,
    )
    session.add(template)
    session.flush()
    rule = TriggerRule(
        tenant_id=tenant_id, event="lead.created", channel="WHATSAPP",
        template_id=template.id, enabled=True, delay_minutes=delay_minutes,
    )
    session.add(rule)
    session.flush()
    return rule


def test_emit_event_creates_queued_delivery_and_is_idempotent(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, user = _tenant_and_user(session)
        _rule_and_template(session, tenant.id)
        entity_id = uuid4()
        deliveries = emit_event(
            session, tenant_id=tenant.id, event="lead.created",
            context={"entity_type": "lead", "entity_id": entity_id, "first_name": "Asha", "project_name": "Skyline", "to_address": "+919800000000"},
        )
        assert len(deliveries) == 1
        delivery = deliveries[0]
        assert delivery.status == DeliveryStatus.QUEUED.value
        assert "Asha" in delivery.body and "Skyline" in delivery.body
        assert delivery.to_address == "+919800000000"

        # Same event/entity/rule is a no-op (idempotent retry).
        again = emit_event(
            session, tenant_id=tenant.id, event="lead.created",
            context={"entity_type": "lead", "entity_id": entity_id, "first_name": "Asha", "project_name": "Skyline", "to_address": "+919800000000"},
        )
        assert again[0].id == delivery.id
        assert session.query(MessageDelivery).count() == 1


def test_delayed_delivery_is_not_sent_before_due_time(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, _ = _tenant_and_user(session)
        _rule_and_template(session, tenant.id, delay_minutes=30)
        emit_event(
            session, tenant_id=tenant.id, event="lead.created",
            context={"entity_type": "lead", "entity_id": uuid4(), "first_name": "Asha", "project_name": "P", "to_address": "+919800000000"},
        )
        session.commit()

    provider = _RecordingProvider()
    with test_session_factory() as session:
        counts = process_due_deliveries(session, now=datetime.now(UTC), provider_factory=lambda name, settings: provider)
        assert counts == {"sent": 0, "retrying": 0, "failed": 0}
        assert provider.sent == []


def test_dispatcher_sends_and_is_idempotent_after_commit(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, _ = _tenant_and_user(session)
        _rule_and_template(session, tenant.id)
        emit_event(
            session, tenant_id=tenant.id, event="lead.created",
            context={"entity_type": "lead", "entity_id": uuid4(), "first_name": "Asha", "project_name": "P", "to_address": "+919800000000"},
        )
        session.commit()

    provider = _RecordingProvider()
    with test_session_factory() as session:
        counts = process_due_deliveries(session, provider_factory=lambda name, settings: provider)
        assert counts["sent"] == 1
        assert len(provider.sent) == 1

    # Second tick finds nothing due (SENT rows are not QUEUED).
    with test_session_factory() as session:
        counts = process_due_deliveries(session, provider_factory=lambda name, settings: provider)
        assert counts["sent"] == 0
        assert len(provider.sent) == 1


def test_provider_failure_retries_then_fails_after_max_attempts(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, _ = _tenant_and_user(session)
        _rule_and_template(session, tenant.id)
        emit_event(
            session, tenant_id=tenant.id, event="lead.created",
            context={"entity_type": "lead", "entity_id": uuid4(), "first_name": "Asha", "project_name": "P", "to_address": "+919800000000"},
        )
        session.commit()

    provider = _RecordingProvider(fail=True)
    with test_session_factory() as session:
        counts = process_due_deliveries(session, provider_factory=lambda name, settings: provider)
        assert counts["retrying"] == 1
        row = session.query(MessageDelivery).one()
        assert row.status == DeliveryStatus.QUEUED.value
        assert row.attempts == 1

        # Exhaust retries; each attempt advances past the exponential delay.
        tick = datetime.now(UTC)
        for _ in range(row.max_attempts + 1):
            tick += timedelta(days=1)
            process_due_deliveries(
                session,
                now=tick,
                provider_factory=lambda name, settings: provider,
            )
            if row.status == DeliveryStatus.FAILED.value:
                break
        assert row.status == DeliveryStatus.FAILED.value
        assert row.error and "provider outage" in row.error
