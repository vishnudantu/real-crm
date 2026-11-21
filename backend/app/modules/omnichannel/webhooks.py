"""Normalize Meta webhook payloads into channel-agnostic inbound events."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.omnichannel.models import ChannelType


@dataclass(frozen=True)
class InboundChannelEvent:
    """One inbound message extracted from a provider webhook."""

    channel: str
    external_message_id: str | None
    thread_id: str
    sender_handle: str | None
    sender_name: str | None
    text: str | None
    media_url: str | None = None
    content_type: str = "TEXT"
    raw: dict = field(default_factory=dict, repr=False)


def _entry_timestamp_ms(entry: dict) -> int | None:
    value = entry.get("time")
    return int(value) if isinstance(value, int) else None


def parse_meta_messages(payload: dict, channel: str) -> list[InboundChannelEvent]:
    """Extract inbound messages from a Meta ``messages`` webhook subscription.

    Handles WhatsApp Cloud (``object == 'whatsapp_business_account'``) and
    Messenger/Instagram (``object == 'page'`` / ``'instagram'``) shapes.
    Unknown entries are ignored so new Meta event types never break ingestion.
    """

    object_kind = payload.get("object")
    events: list[InboundChannelEvent] = []
    for entry in payload.get("entry", []) or []:
        if object_kind == "whatsapp_business_account":
            events.extend(_parse_whatsapp_entry(entry))
        elif object_kind in {"page", "instagram"}:
            events.extend(_parse_messenger_entry(entry, channel=channel, object_kind=object_kind))
    return events


def _parse_whatsapp_entry(entry: dict) -> list[InboundChannelEvent]:
    events: list[InboundChannelEvent] = []
    for change in entry.get("changes", []) or []:
        if change.get("field") != "messages":
            continue
        value = change.get("value") or {}
        contacts = {
            str(c.get("wa_id")): (c.get("profile") or {}).get("name")
            for c in value.get("contacts", []) or []
            if isinstance(c, dict)
        }
        metadata_phone = (value.get("metadata") or {}).get("display_phone_number")
        for message in value.get("messages", []) or []:
            sender = str(message.get("from") or "")
            msg_type = message.get("type") or "text"
            text = None
            media_url = None
            content_type = "TEXT"
            if msg_type == "text":
                text = (message.get("text") or {}).get("body")
            elif msg_type in {"image", "audio", "video", "document", "sticker"}:
                media = message.get(msg_type) or {}
                media_url = media.get("id")  # Graph media id; resolved on demand
                text = media.get("caption")
                content_type = msg_type.upper()
            else:
                content_type = str(msg_type).upper()
                text = None
            events.append(
                InboundChannelEvent(
                    channel=ChannelType.WHATSAPP.value,
                    external_message_id=message.get("id"),
                    thread_id=sender,
                    sender_handle=sender,
                    sender_name=contacts.get(sender),
                    text=text,
                    media_url=media_url,
                    content_type=content_type,
                    raw={"metadata_phone": metadata_phone},
                )
            )
    return events


def _parse_messenger_entry(entry: dict, *, channel: str, object_kind: str) -> list[InboundChannelEvent]:
    effective_channel = (
        ChannelType.INSTAGRAM.value if object_kind == "instagram" else channel
    )
    events: list[InboundChannelEvent] = []
    for item in entry.get("messaging", []) or []:
        message = item.get("message")
        if not message:
            continue
        sender = (item.get("sender") or {}).get("id")
        if not sender:
            continue
        text = message.get("text")
        media_url = None
        content_type = "TEXT"
        attachments = message.get("attachments") or []
        if attachments:
            first = attachments[0]
            media_url = (first.get("payload") or {}).get("url")
            content_type = str(first.get("type") or "ATTACHMENT").upper()
        events.append(
            InboundChannelEvent(
                channel=effective_channel,
                external_message_id=message.get("mid"),
                thread_id=str(sender),
                sender_handle=str(sender),
                sender_name=None,
                text=text,
                media_url=media_url,
                content_type=content_type,
                raw={"recipient": (item.get("recipient") or {}).get("id")},
            )
        )
    return events


def parse_simulated_message(payload: dict, channel: str) -> InboundChannelEvent:
    """Parse the deterministic local-test webhook shape."""

    return InboundChannelEvent(
        channel=channel,
        external_message_id=payload.get("external_message_id"),
        thread_id=str(payload.get("thread_id") or payload.get("sender_handle") or ""),
        sender_handle=payload.get("sender_handle"),
        sender_name=payload.get("sender_name"),
        text=payload.get("text"),
        media_url=payload.get("media_url"),
        content_type=str(payload.get("content_type") or "TEXT"),
    )
