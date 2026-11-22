"""Lifecycle message seeding: default templates + trigger rules fire on events."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.auth.security import hash_password
from app.modules.messaging import service
from app.modules.messaging.defaults import DEFAULT_LIFECYCLE_MESSAGES, seed_lifecycle_messages
from app.modules.messaging.engine import emit_event
from app.modules.messaging.models import (
    DeliveryStatus,
    MessageDelivery,
    MessageTemplate,
    TriggerRule,
)
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD


def _tenant_admin(session: Session) -> tuple[Tenant, User]:
    tenant = Tenant(slug=f"msg-{uuid4().hex[:8]}", name="Msg Co")
    session.add(tenant)
    session.flush()
    role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one_or_none()
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    admin = User(
        tenant_id=tenant.id, full_name="Admin", email=f"a.{tenant.id.hex[:8]}@msg.example",
        password_hash=hash_password(TEST_PASSWORD), role_id=role.id, is_active=True,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return tenant, admin


def test_seed_creates_rules_for_all_lifecycle_events(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, _admin = _tenant_admin(session)
        result = seed_lifecycle_messages(session, tenant_id=tenant.id)
        session.commit()
        assert result["rules_created"] == len(DEFAULT_LIFECYCLE_MESSAGES)
        rules = session.scalars(
            select(TriggerRule).where(TriggerRule.tenant_id == tenant.id)
        ).all()
        assert len(rules) == len(DEFAULT_LIFECYCLE_MESSAGES)
        events = {r.event for r in rules}
        assert "site_visit.booked" in events
        assert "site_visit.completed" in events
        assert "document.receipt_issued" in events


def test_emit_event_queues_delivery_with_rendered_body(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, _admin = _tenant_admin(session)
        seed_lifecycle_messages(session, tenant_id=tenant.id)
        session.commit()

        deliveries = emit_event(
            session,
            tenant_id=tenant.id,
            event="site_visit.completed",
            context={
                "entity_type": "booking",
                "entity_id": uuid4(),
                "first_name": "Asha",
                "project_name": "Canopy Towers",
                "to_address": "+919800000000",
            },
        )
        session.commit()
        # Two channels seeded for site_visit.completed: WHATSAPP + EMAIL.
        assert len(deliveries) == 2
        for delivery in deliveries:
            assert delivery.status == DeliveryStatus.QUEUED.value
            assert "Asha" in delivery.body
            assert "Canopy Towers" in delivery.body
            assert "{first_name}" not in delivery.body


def test_seed_is_idempotent_and_preserves_custom_rules(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, _admin = _tenant_admin(session)
        first = seed_lifecycle_messages(session, tenant_id=tenant.id)
        session.commit()
        assert first["rules_created"] == len(DEFAULT_LIFECYCLE_MESSAGES)

        # Re-seed: everything is skipped, nothing duplicated.
        second = seed_lifecycle_messages(session, tenant_id=tenant.id)
        session.commit()
        assert second["rules_created"] == 0
        assert second["skipped"] == len(DEFAULT_LIFECYCLE_MESSAGES)
        count = len(
            session.scalars(
                select(TriggerRule).where(TriggerRule.tenant_id == tenant.id)
            ).all()
        )
        assert count == len(DEFAULT_LIFECYCLE_MESSAGES)


def test_seed_endpoint_returns_counts(
    client, override_db, seeded_roles, test_session_factory, user_factory, auth_headers,
) -> None:
    admin = user_factory(role=RoleName.ADMIN)
    headers = auth_headers(admin.email)
    r = client.post("/api/v1/messaging/seed-lifecycle", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rules_created"] == len(DEFAULT_LIFECYCLE_MESSAGES)
    # Re-seed returns zeros for created.
    again = client.post("/api/v1/messaging/seed-lifecycle", headers=headers)
    assert again.json()["rules_created"] == 0
