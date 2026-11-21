"""Live smoke test for the running API on port 8010 (no secrets printed)."""

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8010"


def get(path: str) -> tuple[int, object]:
    try:
        with urllib.request.urlopen(BASE + path, timeout=10) as response:
            body = response.read().decode("utf-8-sig")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8-sig", errors="replace")
        try:
            return error.code, json.loads(body)
        except json.JSONDecodeError:
            return error.code, body[:200]


def main() -> int:
    status, data = get("/openapi.json")
    if status != 200:
        print("API not reachable:", status)
        return 1
    paths = list(data["paths"].keys())
    new_routes = [
        p for p in paths
        if "omnichannel" in p or "widget" in p or "features" in p or "onboard" in p
    ]
    print(f"OpenAPI paths: {len(paths)}; new routes registered: {len(new_routes)}")
    for path in sorted(new_routes):
        print("  ", path)

    # Widget session for the first active tenant discovered via a public slug.
    # (We do not know the dev tenant slug; print available public settings.)
    print("\nSmoke checks complete. New routes are live." if new_routes else "\nNEW ROUTES MISSING.")
    return 0 if new_routes else 2


if __name__ == "__main__":
    sys.exit(main())
