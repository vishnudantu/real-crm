"""Omnichannel inbox, channel configuration, webhooks, and calling endpoints."""

from __future__ import annotations

import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.auth.dependencies import CurrentUser
from app.modules.omnichannel import repository
from app.modules.omnichannel.calling import end_call, join_call, start_call, start_recording
from app.modules.omnichannel.exceptions import (
    ChannelConfigurationError,
    ChannelConversationNotFoundError,
    ChannelWebhookVerificationError,
    RecordingConsentRequiredError,
)
from app.modules.omnichannel.models import ChannelCredential, ChannelType
from app.modules.omnichannel.schemas import (
    AssignConversationRequest,
    CallJoinRequest,
    CallRecordingResponse,
    CallResponse,
    CallStartRequest,
    CallTokenResponse,
    ChannelConversationDetail,
    ChannelConversationResponse,
    ChannelCredentialResponse,
    ChannelCredentialUpsert,
    ChannelMessageResponse,
    InboxResponse,
    SendChannelMessageRequest,
)
from app.modules.omnichannel.security import verify_hmac_sha256, verify_subscription_token
from app.modules.omnichannel.service import ingest_inbound, send_reply, upsert_credential
from app.modules.omnichannel.webhooks import parse_meta_messages, parse_simulated_message
from app.modules.operator import features
from app.modules.operator.feature_gate import require_feature
from app.modules.tenancy.models import Tenant, TenantStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/omnichannel", tags=["omnichannel"])
webhook_router = APIRouter(prefix="/webhooks/channels", tags=["channel-webhooks"])

INBOX_FEATURE = "omnichannel_inbox"
CALLING_FEATURE = "calling"
CHANNEL_FEATURES = {
    ChannelType.WHATSAPP.value: "channel_whatsapp",
    ChannelType.INSTAGRAM.value: "channel_instagram",
    ChannelType.MESSENGER.value: "channel_messenger",
}


def _manager(user: CurrentUser) -> CurrentUser:
    from app.modules.users.exceptions import InsufficientPermissionsError
    from app.modules.users.models import RoleName

    if user.role.name not in {RoleName.ADMIN.value, RoleName.SALES_EXECUTIVE.value}:
        raise InsufficientPermissionsError()
    return user


# ---------------------------------------------------------------------------
# Channel configuration (admin only)
# ---------------------------------------------------------------------------


def _channel_feature_enabled(db: Session, *, tenant_id: UUID, channel: str) -> bool:
    feature_key = CHANNEL_FEATURES.get(channel)
    if feature_key is None:
        return True
    return features.tenant_feature_state(db, tenant_id=tenant_id, key=feature_key)


@router.put(
    "/credentials/{channel}",
    response_model=ChannelCredentialResponse,
    dependencies=[Depends(require_feature(INBOX_FEATURE))],
)
def configure_channel(
    channel: ChannelType,
    payload: ChannelCredentialUpsert,
    db: Annotated[Session, Depends(get_db)],
    actor: CurrentUser,
):
    if actor.role.name != "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can configure channels.")
    if payload.channel != channel:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Channel path and payload must match.")
    try:
        return upsert_credential(db, actor=actor, payload=payload)
    except ChannelConfigurationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get(
    "/credentials",
    response_model=list[ChannelCredentialResponse],
    dependencies=[Depends(require_feature(INBOX_FEATURE))],
)
def list_channels(db: Annotated[Session, Depends(get_db)], actor: CurrentUser):
    if actor.role.name != "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can view channel configuration.")
    return repository.list_credentials(db, tenant_id=actor.tenant_id)


# ---------------------------------------------------------------------------
# Unified inbox
# ---------------------------------------------------------------------------


@router.get(
    "/inbox",
    response_model=InboxResponse,
    dependencies=[Depends(require_feature(INBOX_FEATURE))],
)
def get_inbox(
    db: Annotated[Session, Depends(get_db)],
    actor: CurrentUser,
    channel: ChannelType | None = None,
    assigned_to_id: UUID | None = None,
    conversation_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    _manager(actor)
    items, total, unread_total = repository.list_inbox(
        db,
        tenant_id=actor.tenant_id,
        channel=channel.value if channel else None,
        assigned_to_id=assigned_to_id,
        status=conversation_status,
        limit=limit,
        offset=offset,
    )
    return InboxResponse(items=items, total=total, unread_total=unread_total)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ChannelConversationDetail,
    dependencies=[Depends(require_feature(INBOX_FEATURE))],
)
def get_conversation(
    conversation_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: CurrentUser,
):
    _manager(actor)
    conversation = repository.get_conversation(
        db, tenant_id=actor.tenant_id, conversation_id=conversation_id, with_messages=True
    )
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
    if conversation.unread_count:
        conversation.unread_count = 0
        db.commit()
    return conversation


@router.post(
    "/conversations/{conversation_id}/assign",
    response_model=ChannelConversationResponse,
    dependencies=[Depends(require_feature(INBOX_FEATURE))],
)
def assign_conversation(
    conversation_id: UUID,
    payload: AssignConversationRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: CurrentUser,
):
    _manager(actor)
    conversation = repository.get_conversation(
        db, tenant_id=actor.tenant_id, conversation_id=conversation_id
    )
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
    conversation.assigned_to_id = payload.assigned_to_id
    db.commit()
    db.refresh(conversation)
    return conversation


@router.post(
    "/messages",
    response_model=ChannelMessageResponse,
    dependencies=[Depends(require_feature(INBOX_FEATURE))],
)
def reply_to_conversation(
    payload: SendChannelMessageRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: CurrentUser,
):
    try:
        return send_reply(
            db, actor=actor, conversation_id=payload.conversation_id, text=payload.text
        )
    except ChannelConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ChannelConfigurationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


# ---------------------------------------------------------------------------
# Calling
# ---------------------------------------------------------------------------


@router.post(
    "/calls",
    response_model=CallTokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_feature(CALLING_FEATURE))],
)
def create_call(
    payload: CallStartRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: CurrentUser,
):
    try:
        call, token, connection = start_call(db, actor=actor, payload=payload)
        return CallTokenResponse(call=call, participant_token=token, connection=connection)
    except RecordingConsentRequiredError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except ChannelConfigurationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post(
    "/calls/{call_id}/join",
    response_model=CallTokenResponse,
    dependencies=[Depends(require_feature(CALLING_FEATURE))],
)
def join_existing_call(
    call_id: UUID,
    payload: CallJoinRequest,
    db: Annotated[Session, Depends(get_db)],
    actor: CurrentUser,
):
    try:
        call, token, connection = join_call(
            db, actor=actor, call_id=call_id, display_name=payload.display_name
        )
        return CallTokenResponse(call=call, participant_token=token, connection=connection)
    except ChannelConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ChannelConfigurationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post(
    "/calls/{call_id}/end",
    response_model=CallResponse,
    dependencies=[Depends(require_feature(CALLING_FEATURE))],
)
def finish_call(call_id: UUID, db: Annotated[Session, Depends(get_db)], actor: CurrentUser):
    try:
        return end_call(db, actor=actor, call_id=call_id)
    except ChannelConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post(
    "/calls/{call_id}/recordings",
    response_model=CallRecordingResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_feature(CALLING_FEATURE))],
)
async def record_call(
    call_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    actor: CurrentUser,
    consent_confirmed: bool = Query(default=False),
):
    try:
        return await start_recording(db, actor=actor, call_id=call_id, consent_confirmed=consent_confirmed)
    except RecordingConsentRequiredError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except ChannelConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ChannelConfigurationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get(
    "/calls/{call_id}/recordings",
    response_model=list[CallRecordingResponse],
    dependencies=[Depends(require_feature(CALLING_FEATURE))],
)
def list_call_recordings(call_id: UUID, db: Annotated[Session, Depends(get_db)], actor: CurrentUser):
    call = repository.get_call(db, tenant_id=actor.tenant_id, call_id=call_id)
    if call is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Call not found.")
    return call.recordings


# ---------------------------------------------------------------------------
# Public webhooks (per-tenant signature verification)
# ---------------------------------------------------------------------------


def _load_active_tenant(db: Session, tenant_id: UUID) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.status != TenantStatus.ACTIVE.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown or inactive organization.")
    return tenant


def _channel_credential(db: Session, tenant_id: UUID, channel: str) -> ChannelCredential | None:
    return db.scalar(
        select(ChannelCredential).where(
            ChannelCredential.tenant_id == tenant_id,
            ChannelCredential.channel == channel,
            ChannelCredential.is_active.is_(True),
        )
    )


@webhook_router.get("/{tenant_id}/{channel}")
def verify_channel_subscription(
    tenant_id: UUID,
    channel: ChannelType,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Meta subscription handshake using this tenant's verify-token digest."""

    _load_active_tenant(db, tenant_id)
    if not features.tenant_feature_state(db, tenant_id=tenant_id, key=INBOX_FEATURE):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Channel ingestion is disabled.")
    if not _channel_feature_enabled(db, tenant_id=tenant_id, channel=channel.value):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Channel is not enabled.")
    credential = _channel_credential(db, tenant_id, channel.value)
    if credential is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Channel is not configured.")
    params = request.query_params
    if not verify_subscription_token(
        mode=params.get("hub.mode"),
        token=params.get("hub.verify_token"),
        stored_hash=credential.webhook_verify_token_hash,
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid subscription verification token.")
    challenge = params.get("hub.challenge")
    if challenge is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing hub.challenge.")
    return int(challenge) if challenge.isdigit() else challenge


@webhook_router.post("/{tenant_id}/{channel}", status_code=status.HTTP_200_OK)
async def receive_channel_webhook(
    tenant_id: UUID,
    channel: ChannelType,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Ingest inbound channel messages after verifying the tenant's signature."""

    _load_active_tenant(db, tenant_id)
    if not features.tenant_feature_state(db, tenant_id=tenant_id, key=INBOX_FEATURE):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Channel ingestion is disabled.")
    if not _channel_feature_enabled(db, tenant_id=tenant_id, channel=channel.value):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Channel is not enabled.")
    credential = _channel_credential(db, tenant_id, channel.value)
    if credential is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Channel is not configured.")
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid JSON payload.") from None

    if credential.provider == "simulated":
        # Local testing only: a simulated provider has no real external sender.
        if credential.config.get("allow_unsigned_simulation") is not True:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Unsigned simulation is disabled.")
        events = [parse_simulated_message(payload, channel.value)]
    else:
        from app.modules.omnichannel.security import decrypt_credentials

        credentials = decrypt_credentials(credential.credentials_ciphertext, tenant_id=tenant_id)
        app_secret = credentials.get("app_secret") or ""
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not verify_hmac_sha256(raw_body=raw_body, secret=app_secret, signature_header=signature):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid webhook signature.")
        events = parse_meta_messages(payload, channel.value)

    ingested = 0
    duplicates = 0
    for event in events:
        existing = repository.find_message_by_external_id(
            db, tenant_id=tenant_id, channel=event.channel, external_message_id=event.external_message_id
        ) if event.external_message_id else None
        if existing is not None:
            duplicates += 1
            continue
        ingest_inbound(db, tenant_id=tenant_id, event=event)
        ingested += 1
    return {"received": len(events), "ingested": ingested, "duplicates": duplicates}
