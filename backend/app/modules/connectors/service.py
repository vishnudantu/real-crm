"""Connector ingestion services: dedupe, lead creation, source attribution, events."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.leads.models import Lead, LeadSource
from app.modules.leads.schemas import LeadCreateRequest
from app.modules.leads.service import create_lead
from app.modules.messaging.engine import emit_event


def ingest_lead(
    session: Session,
    *,
    tenant_id: UUID,
    project_id: UUID,
    full_name: str,
    email: str | None,
    phone: str | None,
    source: LeadSource,
    external_id: str | None = None,
    source_detail: str | None = None,
) -> Lead | None:
    """Create a connector lead; returns None when the contact already exists."""

    # Dedupe by normalized email/phone within the tenant.
    conditions = [Lead.tenant_id == tenant_id]
    if email:
        conditions.append(Lead.email == email.strip().lower())
    if phone:
        conditions.append(Lead.phone == phone)
    if len(conditions) == 1:
        return None
    existing = session.scalar(select(Lead).where(*conditions).limit(1))
    if existing is not None:
        return None

    payload = LeadCreateRequest(
        full_name=full_name,
        email=email,
        phone=phone,
        project_id=project_id,
        source=source,
        consent_to_contact=True,
    )
    created = create_lead(session, payload=payload)
    if external_id:
        from app.modules.connectors.models import LeadIngestionEvent

        session.add(
            LeadIngestionEvent(
                tenant_id=tenant_id,
                lead_id=created.id,
                provider=source_detail or source.value,
                external_id=external_id,
                payload={},
                received_at=datetime.now(UTC),
            )
        )
        session.commit()
    return created
