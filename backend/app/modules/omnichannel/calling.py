"""Browser calling lifecycle with LiveKit rooms and recorded consent."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.modules.omnichannel import repository
from app.modules.omnichannel.exceptions import (
    ChannelConfigurationError,
    ChannelConversationNotFoundError,
    RecordingConsentRequiredError,
)
from app.modules.omnichannel.models import (
    CallDirection,
    CallRecord,
    CallRecording,
    CallStatus,
    RecordingStatus,
)
from app.modules.omnichannel.providers.factory import build_call_provider
from app.modules.omnichannel.schemas import CallStartRequest
from app.modules.omnichannel.service import get_decrypted_config
from app.modules.users.models import RoleName, User

logger = logging.getLogger(__name__)

_CALLING_CHANNEL = "VOICE"
_CALL_ROLES = frozenset({RoleName.ADMIN.value, RoleName.SALES_EXECUTIVE.value})


def _require_caller(user: User) -> None:
    from app.modules.users.exceptions import InsufficientPermissionsError

    if user.role.name not in _CALL_ROLES:
        raise InsufficientPermissionsError()


def start_call(session: Session, *, actor: User, payload: CallStartRequest) -> tuple[CallRecord, str, dict]:
    """Create a call room and issue the agent's participant token.

    Recording requires an explicit consent confirmation: Indian DPDP and
    two-party-consent jurisdictions require disclosure before recording.
    """

    _require_caller(actor)
    if payload.record and not payload.recording_consent_confirmed:
        raise RecordingConsentRequiredError(
            "Confirm that the contact has been informed the call will be recorded."
        )
    credentials, config, provider_name = get_decrypted_config(
        session, tenant_id=actor.tenant_id, channel=_CALLING_CHANNEL
    )
    provider = build_call_provider(provider_name)
    room_name = f"tenant-{actor.tenant_id}-call-{uuid4().hex[:16]}"
    provider.create_room(room_name=room_name, credentials=credentials, config=config)
    call = CallRecord(
        tenant_id=actor.tenant_id,
        lead_id=payload.lead_id,
        conversation_id=payload.conversation_id,
        agent_id=actor.id,
        direction=CallDirection.OUTBOUND.value,
        status=CallStatus.INITIATED.value,
        provider=provider_name,
        room_name=room_name,
        destination=payload.destination,
        caller_identity=f"agent-{actor.id}",
        metadata_json={"record_requested": payload.record},
    )
    session.add(call)
    session.flush()
    token = provider.issue_participant_token(
        room_name=room_name,
        identity=call.caller_identity,
        display_name=actor.full_name,
        credentials=credentials,
        config=config,
    )
    connection = provider.connection_info(credentials=credentials, config=config)
    session.commit()
    session.refresh(call)
    return call, token, connection


def join_call(
    session: Session, *, actor: User, call_id: UUID, display_name: str | None = None
) -> tuple[CallRecord, str, dict]:
    """Issue a participant token for an existing call (agent or guest)."""

    call = repository.get_call(session, tenant_id=actor.tenant_id, call_id=call_id)
    if call is None:
        raise ChannelConversationNotFoundError("Call not found.")
    credentials, config, provider_name = get_decrypted_config(
        session, tenant_id=actor.tenant_id, channel=_CALLING_CHANNEL
    )
    provider = build_call_provider(provider_name)
    identity = f"user-{actor.id}"
    token = provider.issue_participant_token(
        room_name=call.room_name,
        identity=identity,
        display_name=display_name or actor.full_name,
        credentials=credentials,
        config=config,
    )
    connection = provider.connection_info(credentials=credentials, config=config)
    if call.status in {CallStatus.INITIATED.value, CallStatus.RINGING.value}:
        call.status = CallStatus.IN_PROGRESS.value
        from app.modules.omnichannel.models import utcnow

        call.started_at = utcnow()
        session.commit()
        session.refresh(call)
    return call, token, connection


def end_call(session: Session, *, actor: User, call_id: UUID) -> CallRecord:
    """Mark a call completed and finalize duration."""

    call = repository.get_call(session, tenant_id=actor.tenant_id, call_id=call_id)
    if call is None:
        raise ChannelConversationNotFoundError("Call not found.")
    from app.modules.omnichannel.models import utcnow

    now = utcnow()
    call.ended_at = now
    call.status = CallStatus.COMPLETED.value
    if call.started_at is not None:
        started = call.started_at if call.started_at.tzinfo else call.started_at.replace(tzinfo=now.tzinfo)
        call.duration_seconds = max(0, int((now - started).total_seconds()))
    session.commit()
    session.refresh(call)
    return call


async def start_recording(session: Session, *, actor: User, call_id: UUID, consent_confirmed: bool) -> CallRecording:
    """Start Egress recording after consent disclosure."""

    _require_caller(actor)
    if not consent_confirmed:
        raise RecordingConsentRequiredError(
            "Confirm that the contact has been informed the call will be recorded."
        )
    call = repository.get_call(session, tenant_id=actor.tenant_id, call_id=call_id)
    if call is None:
        raise ChannelConversationNotFoundError("Call not found.")
    credentials, config, provider_name = get_decrypted_config(
        session, tenant_id=actor.tenant_id, channel=_CALLING_CHANNEL
    )
    provider = build_call_provider(provider_name)
    if provider_name == "simulated":
        egress_id = provider.start_recording(room_name=call.room_name, credentials=credentials, config=config)
    else:
        egress_id = await provider.start_recording(room_name=call.room_name, credentials=credentials, config=config)
    recording = CallRecording(
        tenant_id=actor.tenant_id,
        call_id=call.id,
        egress_id=egress_id,
        status=RecordingStatus.RECORDING.value,
    )
    session.add(recording)
    session.commit()
    session.refresh(recording)
    return recording
