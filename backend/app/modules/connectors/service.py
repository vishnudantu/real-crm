"""Connector ingestion services: dedupe, lead creation, source attribution, events."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.leads.models import Lead, LeadSource
from app.modules.leads.schemas import LeadCreateRequest, normalize_email, normalize_phone
from app.modules.leads.service import create_lead


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
    consent_basis: str | None = None,
    consent_evidence: dict | None = None,
) -> Lead | None:
    """Create a lead, returning None when normalized email OR phone already exists.

    Contact consent is true only for an explicitly evidenced ``meta_form``
    submission. Other or legacy callers retain no implicit marketing consent.
    """

    normalized_email = normalize_email(email)
    normalized_phone = normalize_phone(phone) if phone else None
    contact_conditions = []
    if normalized_email:
        contact_conditions.append(Lead.email == normalized_email)
    if normalized_phone:
        contact_conditions.append(Lead.phone == normalized_phone)
    if not contact_conditions:
        return None
    existing = session.scalar(
        select(Lead)
        .where(Lead.tenant_id == tenant_id, or_(*contact_conditions))
        .limit(1)
    )
    if existing is not None:
        return None

    payload = LeadCreateRequest(
        full_name=full_name,
        email=email,
        phone=phone,
        project_id=project_id,
        source=source,
        consent_to_contact=consent_basis == "meta_form",
    )
    created = create_lead(session, payload=payload)
    if external_id:
        from app.modules.connectors.models import LeadIngestionEvent

        evidence = dict(consent_evidence) if consent_basis == "meta_form" else {}
        session.add(
            LeadIngestionEvent(
                tenant_id=tenant_id,
                lead_id=created.id,
                provider=source_detail or source.value,
                external_id=external_id,
                payload=evidence,
                received_at=datetime.now(UTC),
            )
        )
        session.commit()
    return created
