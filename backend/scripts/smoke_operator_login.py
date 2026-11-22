"""Smoke: operator login against the live API using the stored local demo credentials.

The password itself is never printed. Usage:
    python scripts/smoke_operator_login.py [path-to-credentials.txt]
Default path: ~/.propflow-demo/operator-credentials.txt
"""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8010/api/v1"


def main() -> int:
    default = pathlib.Path.home() / ".propflow-demo" / "operator-credentials.txt"
    path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else default
    if not path.exists():
        print(f"credentials file not found: {path}")
        return 2
    lines = path.read_text(encoding="utf-8").splitlines()
    email = next((l.split(":", 1)[1].strip() for l in lines if l.strip().startswith("Email:")), "")
    password = next((l.split(":", 1)[1].strip() for l in lines if l.strip().startswith("Password:")), "")
    if not email or not password:
        print("could not parse Email/Password from credentials file")
        return 2

    payload = json.dumps({"email": email, "password": password}).encode()
    request = urllib.request.Request(
        BASE + "/operator/auth/login", data=payload, method="POST"
    )
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            body = json.loads(response.read().decode("utf-8-sig"))
        print(f"operator login: HTTP {response.status}, token received: {bool(body.get('access_token'))}")
    except urllib.error.HTTPError as error:
        print(f"operator login FAILED: HTTP {error.code} {error.read().decode(errors='replace')[:200]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
