"""Public lead-ingestion webhooks with per-connection signature verification."""

from __future__ import annotations

import json
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.connectors.meta_leads import (
    extract_meta_lead_ids,
    fetch_meta_lead,
    map_meta_lead_fields,
    verify_meta_challenge,
    verify_meta_signature,
)
from app.modules.connectors.service import ingest_lead
from app.modules.integrations.models import IntegrationConnection
from app.modules.integrations.service import (
    get_credentials,
    record_error,
    record_success,
    resolve_meta_page,
)
from app.modules.leads.models import LeadSource
from app.modules.omnichannel.security import verify_hmac_sha256, verify_subscription_token
from app.modules.projects.models import Project, ProjectStatus

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_ACCESS_TOKEN_IN_URL = re.compile(r"(access_token=)[^\s&'\"]+")


def _safe_error(exc: Exception) -> str:
    """Redact credentials that providers echo back in request-URL error text."""

    return _ACCESS_TOKEN_IN_URL.sub(r"\1***", str(exc))


def _matches_connection_token(db: Session, *, mode: str | None, token: str | None) -> bool:
    """Authorize Meta's page-agnostic handshake against any active connection."""

    stored_hashes = db.scalars(
        select(IntegrationConnection.webhook_verify_token_hash).where(
            IntegrationConnection.provider == "meta_lead_ads",
            IntegrationConnection.is_active.is_(True),
            IntegrationConnection.webhook_verify_token_hash.is_not(None),
        )
    ).all()
    return any(
        verify_subscription_token(mode=mode, token=token, stored_hash=stored_hash)
        for stored_hash in stored_hashes
    )


@router.get("/meta")
def meta_verify(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Accept the legacy global handshake or a configured connection token."""

    challenge = verify_meta_challenge(
        mode=request.query_params.get("hub.mode"),
        token=request.query_params.get("hub.verify_token"),
        challenge=request.query_params.get("hub.challenge"),
        settings=settings,
    )
    if challenge is None and _matches_connection_token(
        db,
        mode=request.query_params.get("hub.mode"),
        token=request.query_params.get("hub.verify_token"),
    ):
        challenge = request.query_params.get("hub.challenge")
    if challenge is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid Meta verification token.")
    return challenge


@router.post("/meta", status_code=status.HTTP_200_OK)
async def meta_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Authenticate and route every lead through its durable page connection."""

    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid JSON payload.") from None
    if not isinstance(payload, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid JSON payload.")

    records = extract_meta_lead_ids(payload)
    routed: list[tuple[dict, IntegrationConnection | None]] = []
    for record in records:
        page_id = record.get("page_id")
        connection = resolve_meta_page(db, page_id=page_id) if page_id else None
        routed.append((record, connection))
        if connection is None:
            continue
        credentials = get_credentials(connection)
        if not verify_hmac_sha256(
            raw_body=raw_body,
            secret=credentials.get("app_secret", ""),
            signature_header=signature,
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid Meta signature.")

    if not any(connection is not None for _record, connection in routed):
        # Nothing authenticated per-connection; with the legacy global secret
        # configured it still gates unauthenticated deliveries.
        if settings.meta_app_secret is not None and not verify_meta_signature(
            raw_body, signature, settings
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid Meta signature.")

    processed: list[str] = []
    skipped: list[str] = []
    for record, connection in routed:
        if connection is None or not connection.is_active:
            skipped.append(record["leadgen_id"])
            continue
        project = db.get(Project, connection.project_id)
        if (
            project is None
            or project.tenant_id != connection.tenant_id
            or project.status != ProjectStatus.ACTIVE.value
        ):
            record_error(db, connection, "The configured project is missing or inactive.")
            skipped.append(record["leadgen_id"])
            continue
        try:
            credentials = get_credentials(connection)
            lead_data = fetch_meta_lead(
                record["leadgen_id"], settings, credentials.get("access_token")
            )
            fields = map_meta_lead_fields(lead_data.get("field_data", []))
            lead = ingest_lead(
                db,
                tenant_id=connection.tenant_id,
                project_id=connection.project_id,
                full_name=fields["full_name"],
                email=fields["email"],
                phone=fields["phone"],
                source=LeadSource.SOCIAL_MEDIA,
                external_id=record["leadgen_id"],
                source_detail="meta_ads",
                consent_basis="meta_form",
                consent_evidence={
                    "source": "meta_lead_ads",
                    "form_id": record.get("form_id"),
                    "ad_id": record.get("ad_id"),
                    "captured_at": record.get("created_time"),
                },
            )
        except Exception as exc:
            db.rollback()
            record_error(db, connection, f"Meta lead processing failed: {_safe_error(exc)}")
            skipped.append(record["leadgen_id"])
            continue
        record_success(db, connection)
        if lead is not None:
            processed.append(record["leadgen_id"])
        else:
            skipped.append(record["leadgen_id"])
    return {"processed": processed, "skipped": skipped}
