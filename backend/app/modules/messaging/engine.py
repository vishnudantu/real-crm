"""Event-driven rendering and transactional delivery-row creation."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.messaging.models import (
    DeliveryStatus,
    MessageDelivery,
    MessageTemplate,
    TriggerRule,
)
from app.modules.messaging.providers.factory import provider_name

_MERGE_TAG_PATTERN = re.compile(r"\{([a-z][a-z0-9_]*)\}")
MAX_BODY_LENGTH = 4000


def render_template(body: str, context: dict) -> str:
    """Replace merge tags; ``{{name}}`` renders a literal ``{name}``."""

    # Protect escaped double-brace tags, then substitute single-brace tags.
    escaped: list[str] = []
    def stash(match: re.Match[str]) -> str:
        escaped.append(match.group(0)[1:-1])
        return f"\x00ESC{len(escaped) - 1}\x00"

    protected = re.sub(r"\{\{[a-z][a-z0-9_]*\}\}", stash, body)

    def replace(match: re.Match[str]) -> str:
        value = context.get(match.group(1))
        return match.group(0) if value is None else str(value)

    rendered = _MERGE_TAG_PATTERN.sub(replace, protected)
    return re.sub(r"\x00ESC(\d+)\x00", lambda m: escaped[int(m.group(1))], rendered)


def event_idempotency_key(
    *, tenant_id: UUID, event: str, entity_id: UUID, rule_id: UUID
) -> str:
    return f"{tenant_id}:{event}:{entity_id}:{rule_id}"


def emit_event(
    session: Session,
    *,
    tenant_id: UUID,
    event: str,
    context: dict,
    now: datetime | None = None,
) -> list[MessageDelivery]:
    """Queue matching rule deliveries in the caller's existing transaction.

    Never commits: the outbox row is durable only when the domain change commits.
    Duplicate events with the same entity/rule key return the existing delivery.
    """

    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    entity_id = context.get("entity_id")
    recipient = context.get("to_address") or context.get("phone") or context.get("email")
    if entity_id is None or not recipient:
        return []

    rules = list(
        session.scalars(
            select(TriggerRule).where(
                TriggerRule.tenant_id == tenant_id,
                TriggerRule.event == event,
                TriggerRule.enabled.is_(True),
            )
        ).all()
    )
    settings = get_settings()
    deliveries: list[MessageDelivery] = []
    for rule in rules:
        key = event_idempotency_key(
            tenant_id=tenant_id, event=event, entity_id=entity_id, rule_id=rule.id
        )
        existing = session.scalar(
            select(MessageDelivery).where(
                MessageDelivery.tenant_id == tenant_id,
                MessageDelivery.idempotency_key == key,
            )
        )
        if existing is not None:
            deliveries.append(existing)
            continue
        template = session.scalar(
            select(MessageTemplate).where(
                MessageTemplate.id == rule.template_id,
                MessageTemplate.tenant_id == tenant_id,
                MessageTemplate.is_active.is_(True),
            )
        )
        if template is None:
            continue
        rendered = render_template(template.body, context)
        if len(rendered) > MAX_BODY_LENGTH:
            raise ValueError("Rendered message body exceeds the supported length.")
        delivery = MessageDelivery(
            tenant_id=tenant_id,
            channel=rule.channel,
            template_id=template.id,
            trigger_rule_id=rule.id,
            to_address=str(recipient),
            body=rendered,
            provider=provider_name(rule.channel, settings),
            status=DeliveryStatus.QUEUED.value,
            event=event,
            entity_type=context.get("entity_type"),
            entity_id=entity_id,
            idempotency_key=key,
            next_attempt_at=timestamp + timedelta(minutes=rule.delay_minutes),
            created_at=timestamp,
            updated_at=timestamp,
        )
        session.add(delivery)
        session.flush()
        deliveries.append(delivery)
    return deliveries
