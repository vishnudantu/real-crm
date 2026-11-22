"""Verify both demo logins end-to-end through the live API."""

import json
import pathlib
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8010/api/v1"


def login(path: str, email: str, password: str) -> tuple[int, str]:
    payload = json.dumps({"email": email, "password": password}).encode()
    request = urllib.request.Request(BASE + path, data=payload, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Origin", "http://127.0.0.1:5180")
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            body = json.loads(response.read().decode("utf-8-sig"))
            ok = bool(body.get("access_token"))
            cors = response.headers.get("access-control-allow-origin")
            return response.status, f"token={ok} cors={cors}"
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8-sig", errors="replace")[:200]


def main() -> int:
    results = []
    results.append(("tenant admin ", login("/auth/login", "admin@skyline-demo.example", "DemoAdmin@2026")))
    results.append(("sales user   ", login("/auth/login", "sales@skyline-demo.example", "DemoSales@2026")))

    creds = (pathlib.Path.home() / ".propflow-demo" / "operator-credentials.txt").read_text(encoding="utf-8")
    email = next(l.split(":", 1)[1].strip() for l in creds.splitlines() if l.startswith("Email:"))
    password = next(l.split(":", 1)[1].strip() for l in creds.splitlines() if l.startswith("Password:"))
    results.append(("operator     ", login("/operator/auth/login", email, password)))

    failures = 0
    for label, (status, detail) in results:
        flag = "OK " if status == 200 else "FAIL"
        if status != 200:
            failures += 1
        print(f"[{flag}] {label} HTTP {status} {detail}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
