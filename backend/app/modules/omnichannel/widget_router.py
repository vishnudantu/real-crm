"""Public, per-tenant website widget endpoints (chat bubble + lead capture).

These endpoints are reachable from third-party websites, so they use a
dedicated widget-session JWT audience, tenant-scoped data exposure, and
per-visitor rate limiting. No authenticated PropFlow user is involved.
"""

from __future__ import annotations

import logging
import time
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.omnichannel import repository
from app.modules.omnichannel.models import (
    ChannelConversation,
    ChannelMessage,
    ChannelType,
    MessageDirection,
)
from app.modules.omnichannel.widget import (
    create_widget_token,
    decode_widget_token,
    render_embed_script,
)
from app.modules.operator import features
from app.modules.tenancy.models import Tenant, TenantStatus

logger = logging.getLogger(__name__)

widget_router = APIRouter(prefix="/widget", tags=["website-widget"])

WIDGET_FEATURE = "web_widget"


def _widget_enabled(db: Session, tenant: Tenant) -> None:
    if not features.tenant_feature_state(db, tenant_id=tenant.id, key=WIDGET_FEATURE):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The website widget is not enabled.")

_MAX_MESSAGE_LENGTH = 4000
_RATE_LIMIT_PER_MINUTE = 30
_RATE_BUCKETS: dict[str, list[float]] = {}

DEFAULT_FALLBACK_REPLY = (
    "Thanks for reaching out! A sales advisor will confirm this shortly. "
    "Would you like us to call you?"
)


def _rate_limit(key: str) -> None:
    now = time.monotonic()
    bucket = [t for t in _RATE_BUCKETS.get(key, []) if now - t < 60]
    if len(bucket) >= _RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many widget requests. Please wait a minute."
        )
    bucket.append(now)
    _RATE_BUCKETS[key] = bucket
    if len(_RATE_BUCKETS) > 10_000:
        _RATE_BUCKETS.clear()


def _active_tenant_by_slug(db: Session, slug: str) -> Tenant:
    tenant = db.scalar(
        select(Tenant).where(Tenant.slug == slug, Tenant.status == TenantStatus.ACTIVE.value)
    )
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown organization.")
    return tenant


def _widget_state(
    slug: str,
    authorization: str | None,
    db: Session,
) -> tuple[Tenant, ChannelConversation, dict]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Widget session token required.")
    try:
        claims = decode_widget_token(authorization.split(" ", 1)[1])
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from None
    tenant = _active_tenant_by_slug(db, slug)
    if claims["tid"] != str(tenant.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Widget token does not match this site.")
    conversation = repository.get_conversation(
        db, tenant_id=tenant.id, conversation_id=UUID(claims["cid"]), with_messages=True
    )
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Widget session expired.")
    _widget_enabled(db, tenant)
    return tenant, conversation, claims


class WidgetSessionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    visitor_id: str | None = Field(default=None, max_length=64)
    project_id: UUID | None = None


class WidgetChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=_MAX_MESSAGE_LENGTH)


class WidgetLeadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    full_name: str = Field(min_length=2, max_length=255)
    phone: str = Field(min_length=6, max_length=32)
    email: EmailStr | None = None
    consent_to_contact: bool


@widget_router.get("/{slug}/embed.js", response_class=PlainTextResponse)
def serve_embed_script(
    slug: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Serve the self-installing, tenant-themed widget script."""

    tenant = _active_tenant_by_slug(db, slug)
    _widget_enabled(db, tenant)
    branding = dict(tenant.theme_json or {})
    branding.setdefault("brand_name", tenant.brand_name)
    base_url = str(request.base_url).rstrip("/")
    script = render_embed_script(
        widget_base_url=base_url, tenant_slug=tenant.slug, branding=branding
    )
    return PlainTextResponse(script, media_type="application/javascript")


@widget_router.post("/{slug}/session", status_code=status.HTTP_200_OK)
def start_or_resume_session(
    slug: str,
    payload: WidgetSessionRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Create or resume a WEB_CHAT thread for one browser visitor."""

    tenant = _active_tenant_by_slug(db, slug)
    _widget_enabled(db, tenant)
    visitor_id = (payload.visitor_id or "").strip() or uuid4().hex
    _rate_limit(f"session:{tenant.id}:{request.client.host if request.client else 'x'}")

    project_id = payload.project_id
    conversation = repository.find_thread(
        db,
        tenant_id=tenant.id,
        channel=ChannelType.WEB_CHAT.value,
        external_thread_id=visitor_id,
    )
    if conversation is None:
        conversation = ChannelConversation(
            tenant_id=tenant.id,
            channel=ChannelType.WEB_CHAT.value,
            external_thread_id=visitor_id,
            contact_handle=visitor_id,
        )
        db.add(conversation)
        db.flush()
    if project_id is not None:
        from app.modules.projects.models import Project, ProjectStatus

        project_ok = db.scalar(
            select(Project.id).where(
                Project.id == project_id,
                Project.tenant_id == tenant.id,
                Project.status == ProjectStatus.ACTIVE.value,
            )
        )
        if project_ok is None:
            project_id = None
    db.commit()
    token = create_widget_token(
        tenant_id=tenant.id,
        conversation_id=conversation.id,
        visitor_id=visitor_id,
        project_id=project_id,
    )
    branding = tenant.theme_json or {}
    return {
        "widget_token": token,
        "visitor_id": visitor_id,
        "conversation_id": str(conversation.id),
        "brand": {
            "name": branding.get("brand_name") or tenant.brand_name,
            "color": branding.get("primary_color") or "#2563eb",
        },
    }


@widget_router.post("/{slug}/chat", status_code=status.HTTP_200_OK)
def widget_chat(
    slug: str,
    payload: WidgetChatRequest,
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
):
    """Answer a visitor with the tenant's AI, grounded in approved facts."""

    tenant, conversation, claims = _widget_state(slug, authorization, db)
    _rate_limit(f"chat:{tenant.id}:{claims['sub']}")

    message = ChannelMessage(
        tenant_id=tenant.id,
        conversation_id=conversation.id,
        channel=ChannelType.WEB_CHAT.value,
        direction=MessageDirection.INBOUND.value,
        sender_handle=claims["sub"],
        content=payload.message.strip(),
        content_type="TEXT",
        status="RECEIVED",
    )
    db.add(message)
    conversation.last_message_preview = message.content[:500]
    conversation.last_message_at = message.created_at
    conversation.unread_count = (conversation.unread_count or 0) + 1
    db.commit()

    reply = _grounded_reply(db, tenant=tenant, project_id=claims.get("pid"), question=message.content)
    outbound = ChannelMessage(
        tenant_id=tenant.id,
        conversation_id=conversation.id,
        channel=ChannelType.WEB_CHAT.value,
        direction=MessageDirection.OUTBOUND.value,
        content=reply,
        content_type="TEXT",
        status="SENT",
    )
    db.add(outbound)
    conversation.last_message_preview = reply[:500]
    conversation.last_message_at = outbound.created_at
    db.commit()
    return {"reply": reply, "message_id": str(outbound.id)}


def _grounded_reply(db: Session, *, tenant: Tenant, project_id: str | None, question: str) -> str:
    """Reuse the approved-facts AI boundary; degrade gracefully without keys."""

    from app.modules.ai_assistant.prompts import build_system_message
    from app.modules.ai_assistant.provider import resolve_ai_client
    from app.modules.projects.models import Project, ProjectStatus
    from app.modules.projects.service import get_approved_facts

    project = None
    if project_id:
        try:
            project = db.get(Project, UUID(project_id))
        except (ValueError, TypeError):
            project = None
        if project is None or project.tenant_id != tenant.id:
            project = None
    if project is None:
        project = db.scalar(
            select(Project)
            .where(Project.tenant_id == tenant.id, Project.status == ProjectStatus.ACTIVE.value)
            .order_by(Project.created_at)
            .limit(1)
        )
    if project is None:
        return DEFAULT_FALLBACK_REPLY

    facts = get_approved_facts(db, project.id, tenant_id=tenant.id)
    system_prompt = build_system_message(
        facts, project_name=project.name, rera_number=project.rera_number
    )
    client = resolve_ai_client()
    try:
        if not client.is_configured:
            return DEFAULT_FALLBACK_REPLY
        return client.generate_chat_completion(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": question}],
        )
    except Exception:
        logger.info("Widget AI reply failed; using fallback.", exc_info=True)
        return DEFAULT_FALLBACK_REPLY


@widget_router.post("/{slug}/lead", status_code=status.HTTP_201_CREATED)
def widget_lead(
    slug: str,
    payload: WidgetLeadRequest,
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
):
    """Capture a contact form submission as a WEBSITE lead."""

    if not payload.consent_to_contact:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Contact consent is required before we can reach out (DPDP).",
        )
    tenant, conversation, claims = _widget_state(slug, authorization, db)
    _rate_limit(f"lead:{tenant.id}:{claims['sub']}")

    from app.modules.leads.schemas import LeadCreateRequest
    from app.modules.leads.service import create_lead
    from app.modules.projects.models import Project, ProjectStatus

    project_id = claims.get("pid")
    project = None
    if project_id:
        try:
            project = db.get(Project, UUID(project_id))
        except (ValueError, TypeError):
            project = None
        if project is None or project.tenant_id != tenant.id:
            project = None
    if project is None:
        project = db.scalar(
            select(Project)
            .where(Project.tenant_id == tenant.id, Project.status == ProjectStatus.ACTIVE.value)
            .order_by(Project.created_at)
            .limit(1)
        )
    if project is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "This organization has no active project to route enquiries."
        )

    from app.modules.leads.models import LeadSource

    lead = create_lead(
        db,
        actor=None,
        payload=LeadCreateRequest(
            full_name=payload.full_name,
            email=payload.email,
            phone=payload.phone,
            project_id=project.id,
            source=LeadSource.WEBSITE,
            consent_to_contact=True,
        ),
    )
    if conversation.lead_id is None:
        conversation.lead_id = lead.id
        db.commit()
    return {"lead_id": str(lead.id)}
