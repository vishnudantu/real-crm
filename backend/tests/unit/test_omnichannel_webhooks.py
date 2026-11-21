"""Unit tests for omnichannel webhook parsing and webhook security helpers."""

from __future__ import annotations

import hashlib
import hmac

import pytest

from app.modules.omnichannel.models import ChannelType
from app.modules.omnichannel.security import (
    hash_verify_token,
    verify_hmac_sha256,
    verify_subscription_token,
)
from app.modules.omnichannel.webhooks import (
    parse_meta_messages,
    parse_simulated_message,
)


def _sign(raw: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


class TestSignatureVerification:
    def test_valid_signature_passes(self) -> None:
        body = b'{"object":"page"}'
        secret = "tenant-app-secret"
        assert verify_hmac_sha256(
            raw_body=body, secret=secret, signature_header=_sign(body, secret)
        )

    def test_tampered_body_fails(self) -> None:
        secret = "tenant-app-secret"
        body = b'{"object":"page"}'
        assert not verify_hmac_sha256(
            raw_body=b'{"object":"evil"}',
            secret=secret,
            signature_header=_sign(body, secret),
        )

    def test_missing_signature_fails(self) -> None:
        assert not verify_hmac_sha256(raw_body=b"{}", secret="s", signature_header="")

    def test_empty_secret_fails(self) -> None:
        body = b"{}"
        assert not verify_hmac_sha256(
            raw_body=body, secret="", signature_header=_sign(body, "other")
        )


class TestSubscriptionTokens:
    def test_matching_verify_token(self) -> None:
        stored = hash_verify_token("my-verify-token")
        assert verify_subscription_token(
            mode="subscribe", token="my-verify-token", stored_hash=stored
        )

    def test_wrong_token_rejected(self) -> None:
        stored = hash_verify_token("my-verify-token")
        assert not verify_subscription_token(
            mode="subscribe", token="attacker", stored_hash=stored
        )

    def test_wrong_mode_rejected(self) -> None:
        assert not verify_subscription_token(
            mode="unsubscribe", token="t", stored_hash=hash_verify_token("t")
        )


class TestWhatsAppParsing:
    def test_inbound_text_message(self) -> None:
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "contacts": [
                                    {"wa_id": "919800000001", "profile": {"name": "Asha"}}
                                ],
                                "messages": [
                                    {
                                        "from": "919800000001",
                                        "id": "wamid.ABC",
                                        "type": "text",
                                        "text": {"body": "Is the 3BHK available?"},
                                    }
                                ],
                            },
                        }
                    ]
                }
            ],
        }
        events = parse_meta_messages(payload, ChannelType.WHATSAPP.value)
        assert len(events) == 1
        event = events[0]
        assert event.channel == ChannelType.WHATSAPP.value
        assert event.thread_id == "919800000001"
        assert event.sender_name == "Asha"
        assert event.text == "Is the 3BHK available?"
        assert event.external_message_id == "wamid.ABC"

    def test_image_message_captures_media_id(self) -> None:
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messages": [
                                    {
                                        "from": "919800000002",
                                        "id": "wamid.IMG",
                                        "type": "image",
                                        "image": {"id": "media-123", "caption": "flat photo"},
                                    }
                                ]
                            },
                        }
                    ]
                }
            ],
        }
        events = parse_meta_messages(payload, ChannelType.WHATSAPP.value)
        assert events[0].content_type == "IMAGE"
        assert events[0].media_url == "media-123"
        assert events[0].text == "flat photo"


class TestMessengerAndInstagramParsing:
    def test_messenger_message(self) -> None:
        payload = {
            "object": "page",
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "psid-1"},
                            "recipient": {"id": "page-1"},
                            "message": {"mid": "m.1", "text": "Hi from FB"},
                        }
                    ]
                }
            ],
        }
        events = parse_meta_messages(payload, ChannelType.MESSENGER.value)
        assert events[0].channel == ChannelType.MESSENGER.value
        assert events[0].thread_id == "psid-1"
        assert events[0].text == "Hi from FB"

    def test_instagram_object_routes_to_instagram(self) -> None:
        payload = {
            "object": "instagram",
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "ig-1"},
                            "message": {"mid": "m.2", "text": "Story reply"},
                        }
                    ]
                }
            ],
        }
        events = parse_meta_messages(payload, ChannelType.MESSENGER.value)
        assert events[0].channel == ChannelType.INSTAGRAM.value

    def test_echo_without_text_is_kept(self) -> None:
        # Bot/agent echoes carry no text; parser must not crash.
        payload = {
            "object": "page",
            "entry": [
                {"messaging": [{"sender": {"id": "p1"}, "message": {"mid": "m3", "echo": True}}]}
            ],
        }
        events = parse_meta_messages(payload, ChannelType.MESSENGER.value)
        assert events[0].text is None


class TestUnknownPayloads:
    def test_empty_entry_is_ignored(self) -> None:
        assert parse_meta_messages({"object": "page", "entry": []}, "MESSENGER") == []

    def test_unknown_object_is_ignored(self) -> None:
        assert parse_meta_messages({"object": "unknown", "entry": [{}]}, "MESSENGER") == []

    def test_non_messages_changes_are_ignored(self) -> None:
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{"changes": [{"field": "statuses", "value": {}}]}],
        }
        assert parse_meta_messages(payload, "WHATSAPP") == []


def test_simulated_message_shape() -> None:
    event = parse_simulated_message(
        {
            "external_message_id": "sim-1",
            "thread_id": "user-42",
            "sender_handle": "user-42",
            "text": "hello",
        },
        ChannelType.WHATSAPP.value,
    )
    assert event.external_message_id == "sim-1"
    assert event.text == "hello"
