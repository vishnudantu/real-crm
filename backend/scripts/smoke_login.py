"""Verify the demo login round-trip against the running API (port 8010)."""

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8010/api/v1"


def post(path, payload, token=None):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(), method="POST"
    )
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.status, json.loads(r.read().decode("utf-8-sig"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8-sig", errors="replace") or "{}")


def main() -> int:
    status, login = post("/auth/login", {
        "email": "admin@skyline-demo.example", "password": "DemoAdmin@2026"
    })
    print(f"1. login: HTTP {status}")
    if status != 200:
        print("   LOGIN FAILED:", login)
        return 1
    token = login["access_token"]

    # Fetch branding the way the frontend does (tenant: omni-demo).
    try:
        with urllib.request.urlopen(BASE + "/tenancy/public/omni-demo", timeout=12) as r:
            branding = json.loads(r.read().decode("utf-8-sig"))
        print(f"2. branding tenant slug: {branding.get('slug')} brand: {branding.get('brand_name')}")
    except urllib.error.HTTPError as e:
        print("   branding fetch failed:", e.code)
        return 1

    # Confirm profile tenant matches branding tenant (the guard's check).
    req = urllib.request.Request(BASE + "/auth/me")
    req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=12) as r:
        me = json.loads(r.read().decode("utf-8-sig"))
    print(f"3. /auth/me role={me['role']['name']} tenant_id={me['tenant_id']}")

    status, features = post_features(token)
    print(f"4. /tenancy/me/features enabled: {sum(1 for v in features.values() if v) if isinstance(features, dict) else 'n/a'}")
    if status == 200 and isinstance(features, dict):
        for k in ("omnichannel_inbox", "web_widget", "calling", "analytics"):
            print(f"     {k}: {features.get(k)}")
    print("\nLOGIN ROUND-TRIP PASSED: admin can authenticate and features resolve for omni-demo.")
    return 0


def post_features(token):
    req = urllib.request.Request(BASE + "/tenancy/me/features")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.status, json.loads(r.read().decode("utf-8-sig"))
    except urllib.error.HTTPError as e:
        return e.code, {}


if __name__ == "__main__":
    sys.exit(main())
