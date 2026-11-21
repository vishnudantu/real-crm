"""End-to-end live widget smoke test against the running API (port 8010).

Uses the real dev database (read-only tenant discovery) and exercises the
public widget surface exactly as a third-party website would.
"""

import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8010"
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "keylo_dev.db")


def request(method: str, path: str, payload: dict | None = None, token: str | None = None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read().decode("utf-8-sig")
            try:
                return response.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return response.status, raw
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8-sig", errors="replace")
        try:
            return error.code, json.loads(raw)
        except json.JSONDecodeError:
            return error.code, raw[:300]


def main() -> int:
    # Discover an active tenant slug from the dev DB (read-only).
    with sqlite3.connect(DB) as conn:
        row = conn.execute(
            "SELECT slug FROM tenants WHERE status='active' ORDER BY created_at LIMIT 1"
        ).fetchone()
        if row is None:
            print("No active tenant found in dev DB; cannot run widget E2E.")
            return 2
        slug = row[0]
    print(f"Testing widget against tenant slug: {slug}")

    # 1. embed.js served
    status, body = request("GET", f"/api/v1/widget/{slug}/embed.js")
    print(f"1. embed.js: HTTP {status} ({len(body) if isinstance(body, str) else 'n/a'} chars)")
    assert status == 200 and "propflowWidget" in body, body

    # 2. session issues a widget token
    status, session = request("POST", f"/api/v1/widget/{slug}/session", {"visitor_id": None})
    print(f"2. session: HTTP {status}, visitor={session.get('visitor_id')}")
    assert status == 200 and session.get("widget_token"), session
    token = session["widget_token"]

    # 3. chat returns a grounded reply (AI may fall back if no key configured)
    status, chat = request(
        "POST", f"/api/v1/widget/{slug}/chat", {"message": "What projects are available?"}, token
    )
    print(f"3. chat: HTTP {status}, reply: {str(chat.get('reply'))[:90]}")
    assert status == 200 and chat.get("reply"), chat

    # 4. lead capture respects DPDP consent
    status, rejected = request(
        "POST",
        f"/api/v1/widget/{slug}/lead",
        {"full_name": "Smoke Test", "phone": "919999999999", "consent_to_contact": False},
        token,
    )
    print(f"4a. lead without consent: HTTP {status} (expected 400)")
    assert status == 400, rejected

    status, lead = request(
        "POST",
        f"/api/v1/widget/{slug}/lead",
        {"full_name": "Smoke Test Buyer", "phone": "919999999998", "consent_to_contact": True},
        token,
    )
    print(f"4b. lead with consent: HTTP {status}, lead_id={lead.get('lead_id')}")
    assert status in (201, 409), lead

    print("\nWIDGET E2E PASSED: embed, session, chat, consent-gated lead capture all live.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
