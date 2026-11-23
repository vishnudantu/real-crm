"""Post-visit thank-you and sale-booking confirmation default templates.

Acceptance:
- DEFAULT_LIFECYCLE_MESSAGES seeds an enabled VISIT_THANK_YOU template pair
  (WHATSAPP + EMAIL) for ``site_visit.completed`` that substitutes buyer name,
  project name, unit, and visit date.
- A BOOKING_CONFIRMATION template pair listens on ``sale_booking.created`` and
  substitutes buyer name, project name, unit, booking amount, and receipt
  number.
- Marking a visit booking COMPLETED fires the thank-you outbox event with the
  new context values; creating a sale booking fires the confirmation event.
- Sends stay consent-gated: an opted-out buyer is suppressed at dispatch.
"""

from __future__ import annotations

import re
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.india import format_inr
from app.modules.auth.security import hash_password
from app.modules.bookings import service as bookings_service
from app.modules.bookings.models import BookingStatus, VisitSlot
from app.modules.leads.models import Lead, LeadSource, LeadStatus
from app.modules.messaging import dispatcher
from app.modules.messaging.defaults import (
    DEFAULT_LIFECYCLE_MESSAGES,
    seed_lifecycle_messages,
)
from app.modules.messaging.engine import render_template
from app.modules.messaging.models import (
    DeliveryStatus,
    MessageDelivery,
    MessageTemplate,
    TriggerRule,
)
from app.modules.postsales import service as postsales_service
from app.modules.postsales.schemas import SaleBookingCreateRequest
from app.modules.projects.models import Project, ProjectStatus
from app.modules.tenancy.models import Tenant
from app.modules.users.models import Role, RoleName, User
from tests.support import TEST_PASSWORD

_TAG_PATTERN = re.compile(r"\{([a-z][a-z0-9_]*)\}")

BOOKING_CONFIRMATION_EVENT = "sale_booking.created"
BOOKING_CONFIRMATION_VARIABLES = (
    "first_name",
    "project_name",
    "unit",
    "booking_amount",
    "receipt_number",
)
VISIT_THANK_YOU_VARIABLES = (
    "first_name",
    "project_name",
    "unit",
    "visit_date",
)


class _RecordingProvider:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, *, to: str, body: str, context: dict) -> str:
        self.sent.append((to, body))
        return f"fake-{len(self.sent)}"


def _fixture(session: Session, *, opted_out: bool = False) -> tuple[Tenant, User, Project, Lead]:
    tenant = Tenant(slug=f"bkc-{uuid4().hex[:8]}", name="Booking Msg Co")
    session.add(tenant)
    session.flush()
    role = session.query(Role).filter_by(name=RoleName.ADMIN.value).one_or_none()
    if role is None:
        role = Role(name=RoleName.ADMIN.value)
        session.add(role)
        session.flush()
    admin = User(
        tenant_id=tenant.id, full_name="Admin",
        email=f"a.{tenant.id.hex[:8]}@bkc.example",
        password_hash=hash_password(TEST_PASSWORD), role_id=role.id, is_active=True,
    )
    session.add(admin)
    session.flush()
    project = Project(
        tenant_id=tenant.id, name="Canopy Enclave", slug=f"canopy-{uuid4().hex[:8]}",
        location="Hyderabad", status=ProjectStatus.ACTIVE.value, created_by=admin.id,
    )
    session.add(project)
    session.flush()
    lead = Lead(
        tenant_id=tenant.id, full_name="Asha Verma", email=f"asha.{tenant.id.hex[:8]}@bkc.example",
        phone="+919800000001", project_id=project.id, source=LeadSource.WEBSITE.value,
        status=LeadStatus.CONVERTED.value, consent_to_contact=True, opted_out=opted_out,
    )
    session.add(lead)
    session.commit()
    return tenant, admin, project, lead


def _seeded_templates(session: Session, tenant_id) -> dict[tuple[str, str], MessageTemplate]:
    return {
        (template.name, template.channel): template
        for template in session.scalars(
            select(MessageTemplate).where(MessageTemplate.tenant_id == tenant_id)
        ).all()
    }


# ---------------------------------------------------------------------------
# Template existence + substitution
# ---------------------------------------------------------------------------


def test_seed_creates_booking_confirmation_templates_and_rules(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, _admin, _project, _lead = _fixture(session)
        result = seed_lifecycle_messages(session, tenant_id=tenant.id)
        session.commit()
        assert result["rules_created"] == len(DEFAULT_LIFECYCLE_MESSAGES)

        templates = _seeded_templates(session, tenant.id)
        whatsapp = templates.get(("booking_confirmation", "WHATSAPP"))
        email = templates.get(("booking_confirmation_email", "EMAIL"))
        assert whatsapp is not None and whatsapp.is_active
        assert email is not None and email.is_active

        rules = session.scalars(
            select(TriggerRule).where(
                TriggerRule.tenant_id == tenant.id,
                TriggerRule.event == BOOKING_CONFIRMATION_EVENT,
                TriggerRule.enabled.is_(True),
            )
        ).all()
        assert {rule.channel for rule in rules} == {"WHATSAPP", "EMAIL"}
        assert {str(rule.template_id) for rule in rules} == {
            str(whatsapp.id), str(email.id),
        }


def test_visit_thank_you_templates_declare_new_variables(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, _admin, _project, _lead = _fixture(session)
        seed_lifecycle_messages(session, tenant_id=tenant.id)
        session.commit()
        templates = _seeded_templates(session, tenant.id)

        whatsapp = templates[("visit_thank_you", "WHATSAPP")]
        email = templates[("visit_thank_you_email", "EMAIL")]
        for template in (whatsapp, email):
            for variable in VISIT_THANK_YOU_VARIABLES:
                assert variable in template.variables, (template.name, variable)
            assert "project_name" in template.variables

        for name, channel in (
            ("booking_confirmation", "WHATSAPP"),
            ("booking_confirmation_email", "EMAIL"),
        ):
            template = templates[(name, channel)]
            for variable in BOOKING_CONFIRMATION_VARIABLES:
                assert variable in template.variables, (name, variable)


def test_templates_fully_substitute_with_declared_variables() -> None:
    booking_entries = [
        (event, channel, name, body)
        for event, channel, name, body, _variables in DEFAULT_LIFECYCLE_MESSAGES
        if event == BOOKING_CONFIRMATION_EVENT
    ]
    assert len(booking_entries) == 2
    context = {
        "first_name": "Asha",
        "project_name": "Canopy Enclave",
        "unit": "B-1201",
        "booking_amount": format_inr(1_50_00_00_00),
        "receipt_number": "RCPT-000001",
        "visit_date": "2026-11-23",
    }
    for _event, _channel, _name, body in booking_entries:
        rendered = render_template(body, context)
        assert _TAG_PATTERN.findall(rendered) == [], rendered
        assert "Asha" in rendered
        assert "Canopy Enclave" in rendered
        assert "B-1201" in rendered
        assert format_inr(1_50_00_00_00) in rendered
        assert "RCPT-000001" in rendered


def test_thank_you_templates_substitute_visit_date_and_unit() -> None:
    thank_you_entries = [
        body
        for event, _channel, _name, body, _variables in DEFAULT_LIFECYCLE_MESSAGES
        if event == "site_visit.completed"
    ]
    assert len(thank_you_entries) == 2
    context = {
        "first_name": "Asha",
        "project_name": "Canopy Enclave",
        "unit": "B-1201",
        "visit_date": "2026-11-23",
    }
    for body in thank_you_entries:
        rendered = render_template(body, context)
        assert _TAG_PATTERN.findall(rendered) == [], rendered
        assert "2026-11-23" in rendered
        assert "B-1201" in rendered


# ---------------------------------------------------------------------------
# Events fired from the domain services
# ---------------------------------------------------------------------------


def test_marking_visit_completed_fires_thank_you_event_with_visit_date(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, project, lead = _fixture(session)
        seed_lifecycle_messages(session, tenant_id=tenant.id)
        session.commit()

        start = bookings_service.utcnow().replace(microsecond=0)
        from datetime import timedelta

        slot = VisitSlot(
            tenant_id=tenant.id, project_id=project.id,
            start_time=start + timedelta(days=1), end_time=start + timedelta(days=1, hours=1),
            capacity=1, is_active=True,
        )
        session.add(slot)
        session.commit()

        booking_response = bookings_service.create_booking(
            session, actor=admin,
            payload=bookings_service.BookingCreateRequest(slot_id=slot.id, lead_id=lead.id),
        )
        updated = bookings_service.update_booking_status(
            session, actor=admin, booking_id=booking_response.id,
            payload=bookings_service.BookingStatusUpdateRequest(status=BookingStatus.COMPLETED),
        )
        assert updated.status == BookingStatus.COMPLETED.value
        visit_date = (start + timedelta(days=1)).date().isoformat()

        completed = session.scalars(
            select(MessageDelivery).where(
                MessageDelivery.tenant_id == tenant.id,
                MessageDelivery.event == "site_visit.completed",
            )
        ).all()
        assert len(completed) == 2  # WHATSAPP + EMAIL thank-you
        for delivery in completed:
            assert delivery.status == DeliveryStatus.QUEUED.value
            assert "Asha" in delivery.body
            assert "Canopy Enclave" in delivery.body
            assert visit_date in delivery.body
            assert "{visit_date}" not in delivery.body
            assert "{unit}" not in delivery.body


def test_sale_booking_creation_fires_booking_confirmation_event(
    test_session_factory: sessionmaker[Session],
) -> None:
    with test_session_factory() as session:
        tenant, admin, project, lead = _fixture(session)
        seed_lifecycle_messages(session, tenant_id=tenant.id)
        session.commit()

        booking = postsales_service.create_booking(
            session, actor=admin,
            payload=SaleBookingCreateRequest(
                lead_id=lead.id, unit_number="B-1201", configuration="3 BHK",
                consideration_paise=1_50_00_00_00,
            ),
        )
        assert booking.status == "BOOKED"

        deliveries = session.scalars(
            select(MessageDelivery).where(
                MessageDelivery.tenant_id == tenant.id,
                MessageDelivery.event == BOOKING_CONFIRMATION_EVENT,
            )
        ).all()
        assert len(deliveries) == 2  # WHATSAPP + EMAIL
        amount = format_inr(1_50_00_00_00)
        for delivery in deliveries:
            assert delivery.status == DeliveryStatus.QUEUED.value
            assert delivery.entity_type == "sale_booking"
            assert str(delivery.entity_id) == str(booking.id)
            assert delivery.to_address == "+919800000001"
            assert "Asha" in delivery.body
            assert "B-1201" in delivery.body
            assert "Canopy Enclave" in delivery.body
            assert amount in delivery.body
            assert "{booking_amount}" not in delivery.body


def test_sale_booking_creation_from_hold_conversion_also_fires_event(
    test_session_factory: sessionmaker[Session],
) -> None:
    from app.modules.inventory import service as inventory_service
    from app.modules.inventory.schemas import UnitCreateRequest

    with test_session_factory() as session:
        tenant, admin, project, lead = _fixture(session)
        seed_lifecycle_messages(session, tenant_id=tenant.id)
        unit = inventory_service.create_unit(
            session, actor=admin,
            payload=UnitCreateRequest(
                project_id=project.id, internal_code="B-1201", tower="B", floor="12",
                configuration="3 BHK", carpet_area_sqft=1450, status="AVAILABLE",
            ),
        )
        assert unit.status == "AVAILABLE"
        hold = inventory_service.acquire_hold(
            session, actor=admin, unit_id=unit.id, lead_id=lead.id,
        )
        _converted_hold, _booking = inventory_service.convert_to_booking(
            session, actor=admin, hold_id=hold.id, consideration_paise=1_50_00_00_00,
        )
        deliveries = session.scalars(
            select(MessageDelivery).where(
                MessageDelivery.tenant_id == tenant.id,
                MessageDelivery.event == BOOKING_CONFIRMATION_EVENT,
            )
        ).all()
        assert len(deliveries) == 2


def test_confirmation_is_transactional_for_consent_but_not_opt_out(
    test_session_factory: sessionmaker[Session],
) -> None:
    """Contract performance covers confirmation, not an explicit opt-out."""

    provider = _RecordingProvider()
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session)
        lead.consent_to_contact = False  # not a full opt-out
        seed_lifecycle_messages(session, tenant_id=tenant.id)
        session.commit()
        postsales_service.create_booking(
            session, actor=admin,
            payload=SaleBookingCreateRequest(
                lead_id=lead.id, unit_number="B-1201", consideration_paise=1_50_00_00_00,
            ),
        )

    with test_session_factory() as session:
        counts = dispatcher.process_due_deliveries(
            session, provider_factory=lambda name, settings: provider
        )
        assert counts["sent"] == 2
        assert counts["suppressed"] == 0
        assert len(provider.sent) == 2


# ---------------------------------------------------------------------------
# Consent gating at dispatch
# ---------------------------------------------------------------------------


def test_opted_out_buyer_has_booking_confirmation_suppressed(
    test_session_factory: sessionmaker[Session],
) -> None:
    provider = _RecordingProvider()
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session, opted_out=True)
        seed_lifecycle_messages(session, tenant_id=tenant.id)
        session.commit()
        postsales_service.create_booking(
            session, actor=admin,
            payload=SaleBookingCreateRequest(
                lead_id=lead.id, unit_number="B-1201", consideration_paise=1_50_00_00_00,
            ),
        )
        delivery_ids = [
            delivery.id
            for delivery in session.scalars(
                select(MessageDelivery).where(
                    MessageDelivery.tenant_id == tenant.id,
                    MessageDelivery.event == BOOKING_CONFIRMATION_EVENT,
                )
            ).all()
        ]
        assert len(delivery_ids) == 2

    with test_session_factory() as session:
        counts = dispatcher.process_due_deliveries(
            session, provider_factory=lambda name, settings: provider
        )
        assert counts["suppressed"] == 2
        assert counts["sent"] == 0
        assert provider.sent == []
        for delivery_id in delivery_ids:
            row = session.get(MessageDelivery, delivery_id)
            assert row.status == DeliveryStatus.CANCELLED.value
            assert row.suppressed_reason == "RECIPIENT_OPTED_OUT"


def test_booking_confirmation_sends_for_consented_buyer(
    test_session_factory: sessionmaker[Session],
) -> None:
    provider = _RecordingProvider()
    with test_session_factory() as session:
        tenant, admin, _project, lead = _fixture(session)
        seed_lifecycle_messages(session, tenant_id=tenant.id)
        session.commit()
        postsales_service.create_booking(
            session, actor=admin,
            payload=SaleBookingCreateRequest(
                lead_id=lead.id, unit_number="B-1201", consideration_paise=1_50_00_00_00,
            ),
        )

    with test_session_factory() as session:
        counts = dispatcher.process_due_deliveries(
            session, provider_factory=lambda name, settings: provider
        )
        assert counts["sent"] == 2
        assert counts["suppressed"] == 0
        assert len(provider.sent) == 2
        rows = session.scalars(
            select(MessageDelivery).where(
                MessageDelivery.tenant_id == tenant.id,
                MessageDelivery.event == BOOKING_CONFIRMATION_EVENT,
            )
        ).all()
        assert all(row.status == DeliveryStatus.SENT.value for row in rows)
        assert all(row.suppressed_reason is None for row in rows)
