"""Public lead-ingestion webhooks with signature verification and replay protection."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
from app.modules.leads.models import LeadSource
from app.modules.projects.models import Project, ProjectStatus

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _active_project_for_meta(session: Session, page_id: str | None) -> Project | None:
    """Resolve the project mapped to a Meta page; requires an explicit mapping.

    Phase 4 maps one active project per Meta page via the page's configured
    project slug in the settings store. Without a mapping, no lead is created.
    """

    if not page_id:
        return None
    from app.modules.settings.models import SystemSetting

    mapping = session.get(SystemSetting, ("default", "meta_page_projects"))
    if mapping is None:
        return None
    project_id = (mapping.value or {}).get(page_id)
    if not project_id:
        return None
    project = session.get(Project, project_id)
    if project is None or project.status != ProjectStatus.ACTIVE.value:
        return None
    return project


@router.get("/meta")
def meta_verify(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
):
    challenge = verify_meta_challenge(
        mode=request.query_params.get("hub.mode"),
        token=request.query_params.get("hub.verify_token"),
        challenge=request.query_params.get("hub.challenge"),
        settings=settings,
    )
    if challenge is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid Meta verification token.")
    return challenge


@router.post("/meta", status_code=status.HTTP_200_OK)
async def meta_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_meta_signature(raw_body, signature, settings):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid Meta signature.")

    import json

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid JSON payload.") from None

    processed: list[str] = []
    skipped: list[str] = []
    for record in extract_meta_lead_ids(payload):
        project = _active_project_for_meta(db, record.get("page_id"))
        if project is None:
            skipped.append(record["leadgen_id"])
            continue
        lead_data = fetch_meta_lead(record["leadgen_id"], settings)
        fields = map_meta_lead_fields(lead_data.get("field_data", []))
        lead = ingest_lead(
            db,
            tenant_id=project.tenant_id,
            project_id=project.id,
            full_name=fields["full_name"],
            email=fields["email"],
            phone=fields["phone"],
            source=LeadSource.SOCIAL_MEDIA,
            external_id=record["leadgen_id"],
            source_detail="meta_ads",
        )
        if lead is not None:
            processed.append(record["leadgen_id"])
        else:
            skipped.append(record["leadgen_id"])
    return {"processed": processed, "skipped": skipped}
