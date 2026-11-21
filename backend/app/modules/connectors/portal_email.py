"""Portal email ingestion: parse 99acres/MagicBricks/Housing.com lead emails."""

from __future__ import annotations

import re
from email import message_from_bytes
from email.message import Message
from email.header import decode_header, make_header

_PORTAL_PATTERNS = {
    "99acres": re.compile(r"99acres|@99acres\.com", re.I),
    "magicbricks": re.compile(r"magicbricks|@magicbricks\.com", re.I),
    "housing": re.compile(r"housing\.com|@housing\.com", re.I),
}

_FIELD_PATTERNS = {
    "full_name": re.compile(r"(?:name|buyer|customer)\s*[:\-]\s*([^\n\r]+)", re.I),
    "email": re.compile(r"(?:email|e-mail)\s*[:\-]\s*([\w.+-]+@[\w-]+\.[\w.]+)", re.I),
    "phone": re.compile(r"(?:phone|mobile|contact|tel)\s*[:\-]\s*([+\d][\d\s\-()]{7,18})", re.I),
    "project": re.compile(r"(?:project|property|listing)\s*[:\-]\s*([^\n\r]+)", re.I),
    "budget": re.compile(r"(?:budget|price)\s*[:\-]\s*(.+)", re.I),
}


def _decoded_text(message: Message) -> str:
    if message.is_multipart():
        parts = message.walk()
        texts = []
        for part in parts:
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True) or b""
                texts.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
        return "\n".join(texts)
    payload = message.get_payload(decode=True) or b""
    return payload.decode(message.get_content_charset() or "utf-8", errors="replace")


def _portal_for(sender: str, subject: str) -> str | None:
    combined = f"{sender} {subject}"
    for portal, pattern in _PORTAL_PATTERNS.items():
        if pattern.search(combined):
            return portal
    return None


def parse_portal_email(raw: bytes) -> dict | None:
    """Parse a portal lead email into lead fields; returns None if unrecognized."""

    message = message_from_bytes(raw)
    sender = str(message.get("From", ""))
    subject = str(make_header(decode_header(str(message.get("Subject", "")))))
    portal = _portal_for(sender, subject)
    if portal is None:
        return None

    text = _decoded_text(message)
    if not text.strip():
        return None

    result: dict = {"source_portal": portal, "raw_subject": subject}
    for field, pattern in _FIELD_PATTERNS.items():
        match = pattern.search(text)
        if match:
            result[field] = match.group(1).strip()
    if not result.get("email") and not result.get("phone"):
        # Try a bare email/phone fallback in the body.
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
        phone_match = re.search(r"\+?\d[\d\s\-()]{8,18}", text)
        if email_match:
            result["email"] = email_match.group(0)
        if phone_match:
            result["phone"] = phone_match.group(0).strip()
    return result


def parse_portal_email_id(raw: bytes) -> str:
    """Return a stable idempotency key for a raw email (UID-based dedupe)."""

    import hashlib

    return hashlib.sha256(raw).hexdigest()
