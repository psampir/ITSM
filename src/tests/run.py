# ai-generated: 85% - opencode drafted this self-test runner against the deployed service; reviewed by the student
"""Own tests for svcdesk (Stretch S3).

Runs against SVCDESK_URL (default http://svcdesk:8080), prints one line per failure and, last,
``ITSMLAB-TESTS: passed=<n> failed=<m>``. Exits non-zero when anything failed.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

BASE = os.environ.get("SVCDESK_URL", "http://svcdesk:8080").rstrip("/")

_passed = 0
_failed = 0


def check(name: str, condition: bool) -> None:
    global _passed, _failed
    if condition:
        _passed += 1
    else:
        _failed += 1
        print(f"FAIL {name}")


def request(method: str, path: str, body: dict | None = None, clock: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if clock is not None:
        req.add_header("X-Test-Clock", clock)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw) if raw else None
        except ValueError:
            parsed = None
        return exc.code, parsed


def wait_health() -> None:
    for _ in range(30):
        try:
            status, _ = request("GET", "/health")
            if status == 200:
                return
        except Exception:
            pass
        time.sleep(1)


def create(clock: str, impact: int = 1, urgency: int = 1, vip: bool = False):
    return request(
        "POST",
        "/tickets",
        {
            "title": "self-test ticket",
            "description": "created by the self-test runner",
            "reporter": {"name": "Self Test", "email": None, "vip": vip},
            "impact": impact,
            "urgency": urgency,
        },
        clock=clock,
    )


def main() -> int:
    wait_health()

    status, body = request("GET", "/health")
    check("health", status == 200 and body.get("status") == "ok" and body.get("service") == "svcdesk")

    status, _ = request("GET", "/this-route-does-not-exist-9f3c")
    check("unknown route 404", status == 404)

    status, ticket = create("2026-10-14T10:00:00Z", 1, 1)
    check("create 201 P1 new", status == 201 and ticket.get("state") == "new" and ticket.get("priority") == "P1")
    check("T1 ack due", ticket.get("sla", {}).get("ack_due_at") == "2026-10-14T10:15:00Z")
    check("T1 resolve due", ticket.get("sla", {}).get("resolve_due_at") == "2026-10-14T14:00:00Z")
    tid = ticket["id"]

    status, body = create("2026-10-14T10:00:00Z", 2, 1)
    check("matrix 2,1 -> P2", status == 201 and body.get("priority") == "P2")

    status, body = create("2026-10-14T10:00:00Z", 3, 3)
    check("matrix 3,3 -> P4", status == 201 and body.get("priority") == "P4")

    status, body = create("2026-10-14T10:00:00Z", 3, 3, vip=True)
    check("vip 3,3 -> P2", status == 201 and body.get("priority") == "P2")

    status, _ = request(
        "POST", "/tickets", {"impact": 1, "urgency": 1, "reporter": {"name": "n"}},
        clock="2026-10-14T10:00:00Z",
    )
    check("missing title rejected", status in (400, 422))

    status, _ = create("2026-10-14T10:00:00Z", 5, 1)
    check("impact 5 rejected", status in (400, 422))

    status, _ = request(
        "POST", "/tickets", {"title": "x", "impact": 1, "urgency": "high", "reporter": {"name": "n"}},
        clock="2026-10-14T10:00:00Z",
    )
    check("urgency high rejected", status in (400, 422))

    status, _ = request("POST", f"/tickets/{tid}/start", clock="2026-10-14T10:05:00Z")
    check("start on new 409", status == 409)

    status, body = request("POST", f"/tickets/{tid}/ack", clock="2026-10-14T10:05:00Z")
    check("ack -> acknowledged", status == 200 and body.get("state") == "acknowledged" and body.get("acknowledged_at") == "2026-10-14T10:05:00Z")

    status, body = request("POST", f"/tickets/{tid}/start", clock="2026-10-14T10:06:00Z")
    check("start -> in_progress", status == 200 and body.get("state") == "in_progress")

    status, body = request("POST", f"/tickets/{tid}/resolve", clock="2026-10-14T11:00:00Z")
    check("resolve -> resolved", status == 200 and body.get("state") == "resolved" and body.get("resolved_at") == "2026-10-14T11:00:00Z")

    status, body = request("POST", f"/tickets/{tid}/close", clock="2026-10-14T12:00:00Z")
    check("close -> closed", status == 200 and body.get("state") == "closed")

    status, body = request("POST", f"/tickets/{tid}/reopen", clock="2026-10-15T12:00:00Z")
    check("reopen closed within 7d", status == 200 and body.get("state") == "in_progress" and body.get("closed_at") is None)

    status, body = request("POST", f"/tickets/{tid}/reopen", clock="2026-10-25T12:00:00Z")
    check("reopen closed outside 7d 409", status == 409)

    status, sla = request("GET", f"/tickets/{tid}/sla", clock="2026-10-19T12:00:00Z")
    check(
        "sla report fields",
        status == 200 and {"priority", "ack_due_at", "resolve_due_at", "ack_breached", "resolve_breached", "paused"}.issubset(sla.keys()),
    )

    status, t4 = create("2026-10-17T10:00:00Z", 2, 1)
    check("T4 resolve tie", t4.get("sla", {}).get("resolve_due_at") == "2026-10-19T14:00:00Z")
    check("T4 ack due", t4.get("sla", {}).get("ack_due_at") == "2026-10-19T07:00:00Z")

    print(f"ITSMLAB-TESTS: passed={_passed} failed={_failed}")
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
