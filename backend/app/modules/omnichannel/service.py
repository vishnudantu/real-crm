"""Channel configuration, inbound ingestion, and outbound reply services."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.omnichannel import repository
from app.modules.omnichannel.exceptions import (
    ChannelConfigurationError,
    ChannelConversationNotFoundError,
)
from app.modules.omnichannel.models import (
    ChannelConversation,
    ChannelMessage,
    ChannelType,
    MessageDirection,
)
from app.modules.omnichannel.providers.factory import build_message_provider
from app.modules.omnichannel.schemas import ChannelCredentialUpsert
from app.modules.omnichannel.security import decrypt_credentials, encrypt_credentials, hash_verify_token
from app.modules.omnichannel.webhooks import InboundChannelEvent
from app.modules.users.models import RoleName, User

logger = logging.getLogger(__name__)

_MANAGE_ROLES = frozenset({RoleName.ADMIN.value, RoleName.SALES_EXECUTIVE.value})


def _require_manager(user: User) -> None:
    from app.modules.users.exceptions import InsufficientPermissionsError

    if user.role.name not in _MANAGE_ROLES:
        raise InsufficientPermissionsError()


def upsert_credential(session: Session, *, actor: User, payload: ChannelCredentialUpsert):
    """Store encrypted channel secrets and non-secret routing config."""

    if actor.role.name != RoleName.ADMIN.value:
        from app.modules.users.exceptions import InsufficientPermissionsError

        raise InsufficientPermissionsError()
    from sqlalchemy import select

    from app.modules.omnichannel.models import ChannelCredential

    existing = session.scalar(
        select(ChannelCredential).where(
            ChannelCredential.tenant_id == actor.tenant_id,
            ChannelCredential.channel == payload.channel.value,
        )
    )
    ciphertext = encrypt_credentials(payload.credentials, tenant_id=actor.tenant_id) if payload.credentials else None
    if existing is None:
        if ciphertext is None:
            raise ChannelConfigurationError("Initial channel credentials are required.")
        record = ChannelCredential(
            tenant_id=actor.tenant_id,
            channel=payload.channel.value,
            provider=payload.provider,
            credentials_ciphertext=ciphertext,
            config=payload.config,
            is_active=payload.is_active,
            webhook_verify_token_hash=(
                hash_verify_token(payload.webhook_verify_token) if payload.webhook_verify_token else None
            ),
        )
        session.add(record)
    else:
        if ciphertext is not None:
            existing.credentials_ciphertext = ciphertext
        existing.provider = payload.provider
        existing.config = payload.config
        existing.is_active = payload.is_active
        if payload.webhook_verify_token:
            existing.webhook_verify_token_hash = hash_verify_token(payload.webhook_verify_token)
        record = existing
    session.commit()
    session.refresh(record)
    return record


def get_decrypted_config(session: Session, *, tenant_id: UUID, channel: str) -> tuple[dict, dict, str]:
    """Return (credentials, config, provider) for an active channel."""

    record = repository.get_credential(session, tenant_id=tenant_id, channel=channel)
    if record is None:
        raise ChannelConfigurationError(f"The {channel} channel is not configured for this organization.")
    return decrypt_credentials(record.credentials_ciphertext, tenant_id=tenant_id), record.config, record.provider


def ingest_inbound(session: Session, *, tenant_id: UUID, event: InboundChannelEvent) -> ChannelMessage:
    """Persist an inbound message idempotently and update its thread.

    Auto-linking to an existing lead is by exact phone handle only; a new lead
    is created with ``consent_to_contact=False`` so the contact's inbound
    message does not get treated as marketing consent (DPDP).
    """

    if event.external_message_id:
        existing = repository.find_message_by_external_id(
            session,
            tenant_id=tenant_id,
            channel=event.channel,
            external_message_id=event.external_message_id,
        )
        if existing is not None:
            return existing

    conversation = repository.find_thread(
        session, tenant_id=tenant_id, channel=event.channel, external_thread_id=event.thread_id
    )
    if conversation is None:
        lead_id = _resolve_or_create_lead(session, tenant_id=tenant_id, event=event)
        conversation = ChannelConversation(
            tenant_id=tenant_id,
            channel=event.channel,
            external_thread_id=event.thread_id,
            contact_name=event.sender_name,
            contact_handle=event.sender_handle,
            lead_id=lead_id,
            unread_count=0,
        )
        session.add(conversation)
        session.flush()

    message = ChannelMessage(
        tenant_id=tenant_id,
        conversation_id=conversation.id,
        channel=event.channel,
        direction=MessageDirection.INBOUND.value,
        external_message_id=event.external_message_id,
        sender_handle=event.sender_handle,
        content_type=event.content_type,
        content=event.text,
        media_url=event.media_url,
        status="RECEIVED",
    )
    session.add(message)
    conversation.last_message_preview = (event.text or f"[{event.content_type}]")[:500]
    conversation.last_message_at = message.created_at
    conversation.unread_count = (conversation.unread_count or 0) + 1
    if event.sender_name and not conversation.contact_name:
        conversation.contact_name = event.sender_name
    try:
        session.commit()
    except IntegrityError:
        # Concurrent duplicate webhook delivery: return the stored copy.
        session.rollback()
        if event.external_message_id:
            existing = repository.find_message_by_external_id(
                session,
                tenant_id=tenant_id,
                channel=event.channel,
                external_message_id=event.external_message_id,
            )
            if existing is not None:
                return existing
        raise
    session.refresh(message)
    return message


def _resolve_or_create_lead(session: Session, *, tenant_id: UUID, event: InboundChannelEvent) -> UUID | None:
    """Link to an existing lead by phone handle, else create a consent-safe lead."""

    from sqlalchemy import select

    from app.modules.leads.models import Lead, LeadSource
    from app.modules.leads.schemas import LeadCreateRequest
    from app.modules.leads.service import create_lead
    from app.modules.projects.models import Project, ProjectStatus

    handle = event.sender_handle
    if handle and event.channel == ChannelType.WHATSAPP.value:
        lead = session.scalar(
            select(Lead).where(Lead.tenant_id == tenant_id, Lead.phone == handle).limit(1)
        )
        if lead is not None:
            return lead.id
    # Without a default project mapping we cannot create a lead; keep the
    # thread unlinked rather than guessing a project.
    project = session.scalar(
        select(Project)
        .where(Project.tenant_id == tenant_id, Project.status == ProjectStatus.ACTIVE.value)
        .order_by(Project.created_at)
        .limit(1)
    )
    if project is None:
        return None
    try:
        created = create_lead(
            session,
            payload=LeadCreateRequest(
                full_name=event.sender_name or f"{event.channel.title()} contact",
                phone=handle,
                project_id=project.id,
                source=LeadSource.SOCIAL_MEDIA,
                consent_to_contact=False,
            ),
        )
        session.commit()
        return created.id
    except Exception:
        session.rollback()
        logger.info("Could not auto-create a lead for inbound %s message", event.channel)
        return None


_CHANNEL_FEATURE_KEYS = {
    ChannelType.WHATSAPP.value: "channel_whatsapp",
    ChannelType.INSTAGRAM.value: "channel_instagram",
    ChannelType.MESSENGER.value: "channel_messenger",
}


def send_reply(session: Session, *, actor: User, conversation_id: UUID, text: str) -> ChannelMessage:
    """Send an outbound reply through the tenant's channel provider."""

    _require_manager(actor)
    conversation = repository.get_conversation(
        session, tenant_id=actor.tenant_id, conversation_id=conversation_id
    )
    if conversation is not None:
        from app.modules.operator import features as operator_features

        channel_feature = _CHANNEL_FEATURE_KEYS.get(conversation.channel)
        if channel_feature and not operator_features.tenant_feature_state(
            session, tenant_id=actor.tenant_id, key=channel_feature
        ):
            raise ChannelConfigurationError(
                f"The {conversation.channel} channel is not enabled for your organization."
            )
    if conversation is None:
        raise ChannelConversationNotFoundError("Conversation not found.")
    credentials, config, provider_name = get_decrypted_config(
        session, tenant_id=actor.tenant_id, channel=conversation.channel
    )
    recipient = conversation.contact_handle or conversation.external_thread_id
    message = ChannelMessage(
        tenant_id=actor.tenant_id,
        conversation_id=conversation.id,
        channel=conversation.channel,
        direction=MessageDirection.OUTBOUND.value,
        sender_id=actor.id,
        content=text,
        content_type="TEXT",
        status="SENDING",
    )
    session.add(message)
    session.flush()
    try:
        provider = build_message_provider(conversation.channel, provider_name)
        external_id = provider.send_text(
            recipient=recipient, text=text, credentials=credentials, config=config
        )
        message.external_message_id = external_id or None
        message.status = "SENT"
        message.error = None
    except Exception as exc:
        message.status = "FAILED"
        message.error = str(exc)[:1000]
        session.commit()
        raise
    conversation.last_message_preview = text[:500]
    conversation.last_message_at = message.created_at
    conversation.unread_count = 0
    session.commit()
    session.refresh(message)
    return message
