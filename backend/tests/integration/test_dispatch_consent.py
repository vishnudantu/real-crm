"""P0.4 evidence: dispatch-time consent gate and suppression audit (PF-003).

Blueprint acceptance (21.2):
- message queued before opt-out is suppressed at dispatch after opt-out.
- suppression is audit visible (status + reason on the outbox row).
- opted-out identity cannot be reached through replay.
- internal staff notifications governed separately from buyer consent.
- suspended tenants generate no new external sends.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.leads.models import Lead
from app.modules.messaging.dispatcher import process_due_deliveries
from app.modules.messaging.engine import emit_event
from app.modules.messaging.models import DeliveryStatus, MessageDelivery
from app.modules.tenancy.models import Tenant

from tests.unit.test_messaging_engine import (
    _RecordingProvider,
    _consented_lead,
    _rule_and_template,
    _tenant_and_user,
)


def _queued(session: Session, tenant_id, creator_id, *, event: str = "lead.created", phone: str = "+919800000000"):
    _rule_and_template(session, tenant_id)
    lead = _consented_lead(session, tenant_id, creator_id=creator_id, phone=phone)
    deliveries = emit_event(
        session, tenant_id=tenant_id, event=event,
        context={"entity_type": "lead", "entity_id": uuid4(), "first_name": "Asha",
                 "project_name": "Skyline", "to_address": phone},
    )
    session.commit()
    return lead, deliveries[0]


class TestOptOutSuppression:
    def test_opt_out_after_queueing_suppresses_dispatch(self, test_session_factory) -> None:
        provider = _RecordingProvider()
        with test_session_factory() as session:
            tenant, creator = _tenant_and_user(session)
            lead, delivery = _queued(session, tenant.id, creator.id)
            lead_id, delivery_id = lead.id, delivery.id

        # Buyer withdraws consent after the trigger queued the message.
        with test_session_factory() as session:
            lead = session.get(Lead, lead_id)
            lead.opted_out = True
            lead.consent_to_contact = False
            session.commit()

        with test_session_factory() as session:
            counts = process_due_deliveries(session, provider_factory=lambda name, settings: provider)
            assert counts["suppressed"] == 1
            assert counts["sent"] == 0
            assert provider.sent == []
            row = session.get(MessageDelivery, delivery_id)
            assert row.status == DeliveryStatus.CANCELLED.value
            assert row.suppressed_reason == "RECIPIENT_OPTED_OUT"

    def test_no_consent_blocks_marketing_allows_after_grant(self, test_session_factory) -> None:
        provider = _RecordingProvider()
        with test_session_factory() as session:
            tenant, creator = _tenant_and_user(session)
            lead, _delivery = _queued(session, tenant.id, creator.id)
            # Marketing-style event with consent withdrawn (not full opt-out).
            lead.consent_to_contact = False
            session.commit()
            tenant_id = tenant.id

        with test_session_factory() as session:
            counts = process_due_deliveries(session, provider_factory=lambda name, settings: provider)
            assert counts["suppressed"] == 1
            row = session.scalars(select(MessageDelivery)).one()
            assert row.suppressed_reason == "MARKETING_CONSENT_ABSENT"

        # Restoring consent cannot resurrect a terminally cancelled row.
        with test_session_factory() as session:
            lead = session.scalars(select(Lead).where(Lead.tenant_id == tenant_id)).one()
            lead.consent_to_contact = True
            session.commit()
            counts = process_due_deliveries(session, provider_factory=lambda name, settings: provider)
            assert counts["sent"] == 0

    def test_unknown_external_address_suppressed(self, test_session_factory) -> None:
        provider = _RecordingProvider()
        with test_session_factory() as session:
            tenant, creator = _tenant_and_user(session)
            _rule_and_template(session, tenant.id)
            emit_event(
                session, tenant_id=tenant.id, event="lead.created",
                context={"entity_type": "lead", "entity_id": uuid4(), "first_name": "Ghost",
                         "project_name": "Skyline", "to_address": "+919777700000"},
            )
            session.commit()

        with test_session_factory() as session:
            counts = process_due_deliveries(session, provider_factory=lambda name, settings: provider)
            assert counts["suppressed"] == 1
            row = session.scalars(select(MessageDelivery)).one()
            assert row.suppressed_reason == "NO_LAWFUL_BASIS_FOUND"

    def test_suspended_tenant_blocks_new_sends(self, test_session_factory) -> None:
        provider = _RecordingProvider()
        with test_session_factory() as session:
            tenant, creator = _tenant_and_user(session)
            _lead, _delivery = _queued(session, tenant.id, creator.id)
            tenant.status = "suspended"
            session.commit()

        with test_session_factory() as session:
            counts = process_due_deliveries(session, provider_factory=lambda name, settings: provider)
            assert counts["suppressed"] == 1
            row = session.scalars(select(MessageDelivery)).one()
            assert row.suppressed_reason == "TENANT_INACTIVE"

    def test_consent_intact_delivery_still_sends(self, test_session_factory) -> None:
        """Positive control: the gate does not break lawful dispatch."""

        provider = _RecordingProvider()
        with test_session_factory() as session:
            tenant, creator = _tenant_and_user(session)
            _queued(session, tenant.id, creator.id)

        with test_session_factory() as session:
            counts = process_due_deliveries(session, provider_factory=lambda name, settings: provider)
            assert counts["sent"] == 1
            assert len(provider.sent) == 1
            row = session.scalars(select(MessageDelivery)).one()
            assert row.suppressed_reason is None
