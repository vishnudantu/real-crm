"""Default tenant lifecycle templates + trigger rules for the messaging engine.

These are the messages the product owner explicitly asked for: a thank-you after
a site visit, a booking confirmation, visit reminders, cancellation notices, and
payment receipts. The engine already emits the events; this module makes sure a
tenant actually has a template and an enabled trigger rule listening for them.

Seeding is idempotent: an existing (tenant, event, channel) rule or an existing
(tenant, name, channel, language) template is left untouched, so a tenant's own
edits are never clobbered by a re-seed.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.messaging.models import MessageChannel, MessageTemplate, TriggerRule

# (event, channel, template_name, body)
# Merge tags use the messaging.engine {tag} syntax; {{tag}} renders a literal {tag}.
DEFAULT_LIFECYCLE_MESSAGES: tuple[tuple[str, str, str, str], ...] = (
    (
        "site_visit.booked",
        MessageChannel.WHATSAPP.value,
        "visit_booking_confirmation",
        "Hi {first_name}, your site visit to {project_name} is confirmed. "
        "We look forward to showing you around. Reply to this message if you need to reschedule.",
    ),
    (
        "site_visit.booked",
        MessageChannel.EMAIL.value,
        "visit_booking_confirmation_email",
        "Dear {first_name},\n\nYour site visit to {project_name} is confirmed.\n"
        "Our team will receive you at the site. If you need to reschedule, just reply to this email.\n\n"
        "Thank you for your interest.",
    ),
    (
        "site_visit.completed",
        MessageChannel.WHATSAPP.value,
        "visit_thank_you",
        "Hi {first_name}, thank you for visiting {project_name} today. "
        "It was a pleasure to host you. Our team will follow up with the details you asked for. "
        "If you have any questions in the meantime, just message us here.",
    ),
    (
        "site_visit.completed",
        MessageChannel.EMAIL.value,
        "visit_thank_you_email",
        "Dear {first_name},\n\nThank you for visiting {project_name} today. "
        "We hope the visit helped you picture your future home.\n"
        "We will be in touch shortly with the next steps. Feel free to reply with any questions.\n\n"
        "Warm regards.",
    ),
    (
        "site_visit.cancelled",
        MessageChannel.WHATSAPP.value,
        "visit_cancelled",
        "Hi {first_name}, your site visit to {project_name} has been cancelled. "
        "We would be happy to arrange another time that suits you. Reply to reschedule.",
    ),
    (
        "site_visit.no_show",
        MessageChannel.WHATSAPP.value,
        "visit_missed",
        "Hi {first_name}, we missed you at your {project_name} visit. "
        "We would love to show you around another time. Reply to pick a new slot.",
    ),
    (
        "lead.created",
        MessageChannel.WHATSAPP.value,
        "lead_welcome",
        "Hi {first_name}, thank you for your interest in {project_name}. "
        "Our team has received your enquiry and will reach out shortly to help you.",
    ),
    (
        "lead.status_changed",
        MessageChannel.WHATSAPP.value,
        "lead_status_update",
        "Hi {first_name}, there is an update on your enquiry for {project_name}. "
        "Our team will be in touch with the details soon.",
    ),
    (
        "document.receipt_issued",
        MessageChannel.EMAIL.value,
        "payment_receipt_email",
        "Dear {customer_name},\n\nThank you for your payment. Your receipt {document_number} "
        "for {project_name} (unit {unit_code}) is ready. You can download it from your account.\n\n"
        "Amount: {amount}\n\nThank you.",
    ),
    (
        "document.demand_letter_issued",
        MessageChannel.EMAIL.value,
        "demand_letter_email",
        "Dear {customer_name},\n\nThis is a reminder for your upcoming payment for {project_name} "
        "(unit {unit_code}). Amount due: {amount}, due on {due_date}.\n"
        "Your demand letter {document_number} is attached in your account.\n\n"
        "Please ignore this if you have already paid.",
    ),
)


def seed_lifecycle_messages(session: Session, *, tenant_id: UUID) -> dict[str, int]:
    """Idempotently seed default templates + trigger rules for one tenant.

    Returns counts: {templates_created, rules_created, skipped}. An existing
    template (same tenant/name/channel/language) or an existing rule (same
    tenant/event/channel) is skipped so tenant customizations survive re-seeds.
    """
    templates_created = 0
    rules_created = 0
    skipped = 0

    for event, channel, name, body in DEFAULT_LIFECYCLE_MESSAGES:
        # A rule already listening for this (event, channel) wins; don't duplicate.
        existing_rule = session.scalar(
            select(TriggerRule).where(
                TriggerRule.tenant_id == tenant_id,
                TriggerRule.event == event,
                TriggerRule.channel == channel,
            )
        )
        if existing_rule is not None:
            skipped += 1
            continue

        template = session.scalar(
            select(MessageTemplate).where(
                MessageTemplate.tenant_id == tenant_id,
                MessageTemplate.name == name,
                MessageTemplate.channel == channel,
                MessageTemplate.language == "en",
            )
        )
        if template is None:
            template = MessageTemplate(
                tenant_id=tenant_id,
                name=name,
                channel=channel,
                language="en",
                body=body,
                variables=[],
                is_active=True,
            )
            session.add(template)
            session.flush()  # assign template.id before the rule references it
            templates_created += 1

        rule = TriggerRule(
            tenant_id=tenant_id,
            event=event,
            channel=channel,
            template_id=template.id,
            enabled=True,
            delay_minutes=0,
        )
        session.add(rule)
        rules_created += 1

    session.flush()
    return {
        "templates_created": templates_created,
        "rules_created": rules_created,
        "skipped": skipped,
    }
