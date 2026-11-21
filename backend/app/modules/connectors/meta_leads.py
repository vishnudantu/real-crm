"""Meta Lead Ads webhook verification, signature validation, and lead mapping."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime

from app.core.config import Settings


def verify_meta_signature(raw_body: bytes, signature_header: str, settings: Settings) -> bool:
    """Validate X-Hub-Signature-256 using the shared app secret."""

    secret = settings.meta_app_secret
    if secret is None or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.get_secret_value().encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def verify_meta_challenge(
    *,
    mode: str | None,
    token: str | None,
    challenge: str | None,
    settings: Settings,
) -> str | None:
    """Respond to Meta's hub.challenge subscription handshake."""

    expected = settings.meta_verify_token
    if expected is None or mode != "subscribe" or token != expected.get_secret_value():
        return None
    return challenge


def extract_meta_lead_ids(payload: dict) -> list[dict]:
    """Return Meta leadgen entries as {leadgen_id, created_time} records."""

    results: list[dict] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "leadgen":
                value = change.get("value", {})
                leadgen_id = value.get("leadgen_id")
                if leadgen_id:
                    results.append({
                        "leadgen_id": str(leadgen_id),
                        "created_time": value.get("created_time"),
                        "form_id": value.get("form_id"),
                        "ad_id": value.get("ad_id"),
                        "page_id": value.get("page_id") or entry.get("id"),
                    })
    return results


def map_meta_lead_fields(field_data: list[dict]) -> dict:
    """Map Meta leadgen field_data to PROPFLOW lead attributes."""

    values = {
        (item.get("name") or "").strip().lower(): (item.get("values") or [""])[0]
        for item in field_data
        if isinstance(item, dict)
    }
    full_name = (
        values.get("full_name")
        or " ".join(filter(None, [values.get("first_name"), values.get("last_name")])).strip()
        or "Meta Lead"
    )
    return {
        "full_name": full_name,
        "email": values.get("email") or None,
        "phone": values.get("phone_number") or values.get("phone") or None,
    }


def fetch_meta_lead(leadgen_id: str, settings: Settings) -> dict:
    """Fetch a Meta lead via Graph API; tests use recorded fixtures."""

    import httpx

    token = settings.meta_page_access_token
    if token is None:
        raise RuntimeError("META_PAGE_ACCESS_TOKEN is required to fetch Meta leads.")
    response = httpx.get(
        f"https://graph.facebook.com/v21.0/{leadgen_id}",
        params={"access_token": token.get_secret_value()},
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json()
