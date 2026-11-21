"""Connector parsing and Meta webhook verification tests."""

from __future__ import annotations

import hashlib
import hmac

from app.modules.connectors.meta_leads import (
    extract_meta_lead_ids,
    map_meta_lead_fields,
    verify_meta_challenge,
    verify_meta_signature,
)
from app.modules.connectors.portal_email import parse_portal_email, parse_portal_email_id
from app.core.config import Settings


def _settings() -> Settings:
    return Settings(
        database_url="sqlite:///test.db",
        jwt_secret_key="a-very-long-test-secret-key-for-testing-purposes-only",
        meta_app_secret="meta-secret",
        meta_verify_token="meta-verify",
        meta_page_access_token="meta-page-token",
    )


def test_meta_signature_verification_accepts_valid_and_rejects_invalid() -> None:
    settings = _settings()
    body = b'{"entry":[]}'
    signature = "sha256=" + hmac.new(b"meta-secret", body, hashlib.sha256).hexdigest()
    assert verify_meta_signature(body, signature, settings) is True
    assert verify_meta_signature(body, "sha256=wrong", settings) is False
    assert verify_meta_signature(body, "", settings) is False


def test_meta_challenge_returns_challenge_for_valid_token() -> None:
    settings = _settings()
    assert verify_meta_challenge(mode="subscribe", token="meta-verify", challenge="12345", settings=settings) == "12345"
    assert verify_meta_challenge(mode="subscribe", token="wrong", challenge="12345", settings=settings) is None


def test_extract_meta_lead_ids_and_field_mapping() -> None:
    payload = {
        "entry": [{
            "id": "page-1",
            "changes": [{
                "field": "leadgen",
                "value": {"leadgen_id": "lead-123", "created_time": 1700000000, "page_id": "page-1"},
            }],
        }]
    }
    ids = extract_meta_lead_ids(payload)
    assert ids == [{"leadgen_id": "lead-123", "created_time": 1700000000, "form_id": None, "ad_id": None, "page_id": "page-1"}]

    fields = map_meta_lead_fields([
        {"name": "full_name", "values": ["Asha Patel"]},
        {"name": "email", "values": ["asha@example.com"]},
        {"name": "phone_number", "values": ["+919800000000"]},
    ])
    assert fields == {"full_name": "Asha Patel", "email": "asha@example.com", "phone": "+919800000000"}


def test_portal_email_parsing_extracts_lead_fields_and_portal() -> None:
    raw = (
        b"From: alerts@99acres.com\r\n"
        b"Subject: New lead from 99acres\r\n\r\n"
        b"Name: Asha Patel\nEmail: asha@example.com\nPhone: +919800000000\nProject: Skyline Residences\nBudget: 85 lakhs\n"
    )
    parsed = parse_portal_email(raw)
    assert parsed is not None
    assert parsed["source_portal"] == "99acres"
    assert parsed["full_name"] == "Asha Patel"
    assert parsed["email"] == "asha@example.com"
    assert parsed["phone"] == "+919800000000"
    assert parsed["project"] == "Skyline Residences"
    assert parse_portal_email_id(raw) == parse_portal_email_id(raw)  # stable idempotency


def test_unrecognized_email_returns_none() -> None:
    assert parse_portal_email(b"From: random@example.com\r\nSubject: hi\r\n\r\nhello") is None
