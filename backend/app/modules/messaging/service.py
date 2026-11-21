"""Tenant-scoped messaging admin operations (templates, rules, delivery log, test send)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.messaging.exceptions import (
    MessageDeliveryNotFoundError,
    MessageTemplateNotFoundError,
    TriggerRuleNotFoundError,
    TriggerRuleTemplateMismatchError,
)
from app.modules.messaging.models import (
    DeliveryStatus,
    MessageDelivery,
    MessageTemplate,
    MessageChannel,
    TriggerRule,
)
from app.modules.messaging.providers.factory import provider_name
from app.core.config import get_settings
from app.modules.users.models import User


def _template(session: Session, template_id: UUID, *, tenant_id: UUID) -> MessageTemplate:
    row = session.scalar(
        select(MessageTemplate).where(
            MessageTemplate.id == template_id,
            MessageTemplate.tenant_id == tenant_id,
        )
    )
    if row is None:
        raise MessageTemplateNotFoundError()
    return row


def create_template(session: Session, *, actor: User, payload) -> MessageTemplate:
    row = MessageTemplate(
        tenant_id=actor.tenant_id,
        name=payload.name,
        channel=payload.channel.value,
        language=payload.language.lower(),
        body=payload.body,
        provider_template_name=payload.provider_template_name,
        variables=payload.variables,
        is_active=True,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_templates(session: Session, *, actor: User) -> list[MessageTemplate]:
    return list(
        session.scalars(
            select(MessageTemplate)
            .where(MessageTemplate.tenant_id == actor.tenant_id)
            .order_by(MessageTemplate.created_at.desc())
        ).all()
    )


def update_template(session: Session, *, actor: User, template_id: UUID, payload) -> MessageTemplate:
    row = _template(session, template_id, tenant_id=actor.tenant_id)
    for field in ("name", "body", "provider_template_name", "variables", "is_active"):
        if field in payload.model_fields_set:
            value = getattr(payload, field)
            if value is not None:
                setattr(row, field, value)
    row.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(row)
    return row


def delete_template(session: Session, *, actor: User, template_id: UUID) -> None:
    row = _template(session, template_id, tenant_id=actor.tenant_id)
    session.delete(row)
    session.commit()


def create_rule(session: Session, *, actor: User, payload) -> TriggerRule:
    template = _template(session, payload.template_id, tenant_id=actor.tenant_id)
    if template.channel != payload.channel.value:
        raise TriggerRuleTemplateMismatchError()
    row = TriggerRule(
        tenant_id=actor.tenant_id,
        event=payload.event,
        channel=payload.channel.value,
        template_id=template.id,
        enabled=payload.enabled,
        delay_minutes=payload.delay_minutes,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_rules(session: Session, *, actor: User) -> list[TriggerRule]:
    return list(
        session.scalars(
            select(TriggerRule)
            .where(TriggerRule.tenant_id == actor.tenant_id)
            .order_by(TriggerRule.created_at.desc())
        ).all()
    )


def update_rule(session: Session, *, actor: User, rule_id: UUID, payload) -> TriggerRule:
    row = session.scalar(
        select(TriggerRule).where(
            TriggerRule.id == rule_id,
            TriggerRule.tenant_id == actor.tenant_id,
        )
    )
    if row is None:
        raise TriggerRuleNotFoundError()
    fields = payload.model_fields_set
    if "template_id" in fields and payload.template_id is not None:
        template = _template(session, payload.template_id, tenant_id=actor.tenant_id)
        if template.channel != row.channel:
            raise TriggerRuleTemplateMismatchError()
        row.template_id = template.id
    if "enabled" in fields and payload.enabled is not None:
        row.enabled = payload.enabled
    if "delay_minutes" in fields and payload.delay_minutes is not None:
        row.delay_minutes = payload.delay_minutes
    row.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(row)
    return row


def delete_rule(session: Session, *, actor: User, rule_id: UUID) -> None:
    row = session.scalar(
        select(TriggerRule).where(
            TriggerRule.id == rule_id,
            TriggerRule.tenant_id == actor.tenant_id,
        )
    )
    if row is None:
        raise TriggerRuleNotFoundError()
    session.delete(row)
    session.commit()


def list_deliveries(
    session: Session,
    *,
    actor: User,
    page: int,
    page_size: int,
    status_filter: str | None = None,
    channel: str | None = None,
) -> dict:
    conditions = [MessageDelivery.tenant_id == actor.tenant_id]
    if status_filter:
        conditions.append(MessageDelivery.status == status_filter)
    if channel:
        conditions.append(MessageDelivery.channel == channel)
    total = session.scalar(
        select(func.count()).select_from(MessageDelivery).where(*conditions)
    ) or 0
    rows = list(
        session.scalars(
            select(MessageDelivery)
            .where(*conditions)
            .order_by(MessageDelivery.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    pages = (total + page_size - 1) // page_size if total else 0
    return {"items": rows, "total": total, "page": page, "page_size": page_size, "pages": pages}


def send_test(session: Session, *, actor: User, payload) -> MessageDelivery:
    if payload.template_id is not None:
        template = _template(session, payload.template_id, tenant_id=actor.tenant_id)
        body = payload.body or template.body
        channel = template.channel
        template_id = template.id
    else:
        if not payload.body:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Provide template_id or body.")
        body = payload.body
        channel = payload.channel.value
        template_id = None
    now = datetime.now(UTC)
    row = MessageDelivery(
        tenant_id=actor.tenant_id,
        channel=channel,
        template_id=template_id,
        to_address=payload.to_address,
        body=body,
        provider=provider_name(channel, get_settings()),
        status=DeliveryStatus.QUEUED.value,
        event="message.test",
        idempotency_key=f"test:{uuid4()}",
        next_attempt_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
