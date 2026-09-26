# ai-generated: 85% - opencode drafted the svcdesk API (routes, validation, state machine) from the specification; reviewed and tested by the student
"""svcdesk - service-desk API (Lab 1).

Decisions implemented: C1 = wallclock, C2 = reopen, C3 = vip.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import metrics, sla, store

C1 = "wallclock"
C2 = "reopen"
C3 = "vip"

TEST_CLOCK = os.environ.get("SVCDESK_TEST_CLOCK", "").strip().lower() in {"1", "true"}

MATRIX: dict[tuple[int, int], str] = {
    (1, 1): "P1", (1, 2): "P2", (1, 3): "P3",
    (2, 1): "P2", (2, 2): "P3", (2, 3): "P4",
    (3, 1): "P3", (3, 2): "P4", (3, 3): "P4",
}

FINAL_STATES = {"resolved", "closed"}
REOPEN_WINDOW = timedelta(days=7)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message


class Reporter(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=1, max_length=100)
    email: Optional[str] = None
    vip: bool = False


class TicketCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    reporter: Reporter
    impact: int = Field(ge=1, le=3)
    urgency: int = Field(ge=1, le=3)
    related_to: Optional[str] = None


app = FastAPI(title="svcdesk", version="1.0.0")


@app.exception_handler(ApiError)
async def _handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}})


@app.exception_handler(RequestValidationError)
async def _handle_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = ".".join(str(part) for part in first.get("loc", []) if part != "body") or "body"
    message = f"{loc}: {first.get('msg', 'invalid request')}"
    return JSONResponse(status_code=422, content={"error": {"code": "validation", "message": message}})


@app.exception_handler(StarletteHTTPException)
async def _handle_http(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    code = "not_found" if exc.status_code == 404 else "error"
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": code, "message": str(exc.detail)}})


def now_for(header_value: Optional[str]) -> datetime:
    if TEST_CLOCK and header_value is not None:
        try:
            parsed = datetime.fromisoformat(header_value)
        except ValueError:
            raise ApiError(422, "validation", "X-Test-Clock is not a valid RFC 3339 instant")
        if parsed.tzinfo is None:
            raise ApiError(422, "validation", "X-Test-Clock must include an offset")
        return parsed.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def compute_priority(impact: int, urgency: int, vip: bool) -> str:
    priority = MATRIX[(impact, urgency)]
    if C3 == "vip" and vip and priority in {"P3", "P4"}:
        priority = "P2"
    return priority


def build_ticket(payload: TicketCreate, now: datetime) -> dict:
    priority = compute_priority(payload.impact, payload.urgency, payload.reporter.vip)
    ack_due, resolve_due = sla.due_instants(priority, now, C1 == "wallclock")
    return {
        "id": str(uuid.uuid4()),
        "title": payload.title,
        "description": payload.description,
        "reporter": {
            "name": payload.reporter.name,
            "email": payload.reporter.email,
            "vip": payload.reporter.vip,
        },
        "impact": payload.impact,
        "urgency": payload.urgency,
        "priority": priority,
        "state": "new",
        "created_at": iso(now),
        "acknowledged_at": None,
        "resolved_at": None,
        "closed_at": None,
        "related_to": payload.related_to,
        "sla": {"ack_due_at": iso(ack_due), "resolve_due_at": iso(resolve_due)},
    }


def load_ticket(ticket_id: str) -> dict:
    ticket = store.get(ticket_id)
    if ticket is None:
        raise ApiError(404, "not_found", f"ticket {ticket_id} does not exist")
    return ticket


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "svcdesk"}


@app.post("/tickets", status_code=201)
def create_ticket(
    payload: TicketCreate,
    x_test_clock: Optional[str] = Header(default=None, alias="X-Test-Clock"),
) -> dict:
    now = now_for(x_test_clock)
    ticket = build_ticket(payload, now)
    store.save(ticket)
    return ticket


@app.get("/tickets")
def list_tickets(
    state: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
) -> list[dict]:
    tickets = store.all_tickets()
    if state is not None:
        tickets = [ticket for ticket in tickets if ticket["state"] == state]
    if priority is not None:
        tickets = [ticket for ticket in tickets if ticket["priority"] == priority]
    return tickets


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str) -> dict:
    return load_ticket(ticket_id)


@app.get("/tickets/{ticket_id}/sla")
def get_ticket_sla(
    ticket_id: str,
    x_test_clock: Optional[str] = Header(default=None, alias="X-Test-Clock"),
) -> dict:
    ticket = load_ticket(ticket_id)
    now = now_for(x_test_clock)
    ack_due = parse_iso(ticket["sla"]["ack_due_at"])
    resolve_due = parse_iso(ticket["sla"]["resolve_due_at"])
    acknowledged_at = parse_iso(ticket["acknowledged_at"]) if ticket["acknowledged_at"] else None
    resolved_at = parse_iso(ticket["resolved_at"]) if ticket["resolved_at"] else None

    ack_breached = now > ack_due if acknowledged_at is None else acknowledged_at > ack_due
    resolve_breached = now > resolve_due if resolved_at is None else resolved_at > resolve_due
    paused = (
        ticket["state"] not in FINAL_STATES
        and sla.uses_business_clock(ticket["priority"], C1 == "wallclock")
        and not sla.in_business_window(now)
    )
    return {
        "priority": ticket["priority"],
        "ack_due_at": ticket["sla"]["ack_due_at"],
        "resolve_due_at": ticket["sla"]["resolve_due_at"],
        "ack_breached": ack_breached,
        "resolve_breached": resolve_breached,
        "paused": paused,
    }


def _apply(ticket_id: str, header_value: Optional[str], allowed_from: set[str], mutate) -> dict:
    ticket = load_ticket(ticket_id)
    if ticket["state"] not in allowed_from:
        raise ApiError(409, "invalid_transition", f"cannot act on a ticket in state {ticket['state']}")
    now = now_for(header_value)
    mutate(ticket, now)
    store.save(ticket)
    return ticket


@app.post("/tickets/{ticket_id}/ack")
def acknowledge(
    ticket_id: str,
    x_test_clock: Optional[str] = Header(default=None, alias="X-Test-Clock"),
) -> dict:
    def mutate(ticket: dict, now: datetime) -> None:
        ticket["state"] = "acknowledged"
        ticket["acknowledged_at"] = iso(now)

    return _apply(ticket_id, x_test_clock, {"new"}, mutate)


@app.post("/tickets/{ticket_id}/start")
def start(
    ticket_id: str,
    x_test_clock: Optional[str] = Header(default=None, alias="X-Test-Clock"),
) -> dict:
    def mutate(ticket: dict, _now: datetime) -> None:
        ticket["state"] = "in_progress"

    return _apply(ticket_id, x_test_clock, {"acknowledged"}, mutate)


@app.post("/tickets/{ticket_id}/resolve")
def resolve(
    ticket_id: str,
    x_test_clock: Optional[str] = Header(default=None, alias="X-Test-Clock"),
) -> dict:
    def mutate(ticket: dict, now: datetime) -> None:
        ticket["state"] = "resolved"
        ticket["resolved_at"] = iso(now)

    return _apply(ticket_id, x_test_clock, {"in_progress"}, mutate)


@app.post("/tickets/{ticket_id}/close")
def close(
    ticket_id: str,
    x_test_clock: Optional[str] = Header(default=None, alias="X-Test-Clock"),
) -> dict:
    def mutate(ticket: dict, now: datetime) -> None:
        ticket["state"] = "closed"
        ticket["closed_at"] = iso(now)

    return _apply(ticket_id, x_test_clock, {"resolved"}, mutate)


@app.post("/tickets/{ticket_id}/reopen")
def reopen(
    ticket_id: str,
    x_test_clock: Optional[str] = Header(default=None, alias="X-Test-Clock"),
) -> dict:
    ticket = load_ticket(ticket_id)
    now = now_for(x_test_clock)
    state = ticket["state"]
    if state == "resolved":
        anchor = parse_iso(ticket["resolved_at"])
    elif state == "closed" and C2 == "reopen":
        anchor = parse_iso(ticket["closed_at"])
    else:
        raise ApiError(409, "invalid_transition", f"cannot reopen a ticket in state {state}")
    if now > anchor + REOPEN_WINDOW:
        raise ApiError(409, "reopen_window_expired", "the 7-day reopen window has expired")
    ticket["state"] = "in_progress"
    ticket["resolved_at"] = None
    ticket["closed_at"] = None
    store.save(ticket)
    return ticket


TICKET_PHASES: tuple[tuple[str, str], ...] = (
    ("created", "created_at"),
    ("acknowledged", "acknowledged_at"),
    ("resolved", "resolved_at"),
    ("closed", "closed_at"),
)


@app.post("/dora/metrics")
async def dora_metrics(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        raise ApiError(400, "invalid_body", "the request body is not valid JSON")
    if not isinstance(body, dict):
        raise ApiError(422, "validation", "the request body must be a JSON object")

    window = body.get("window")
    if not isinstance(window, dict):
        raise ApiError(422, "validation", "window is required and must be an object")
    raw_from = window.get("from")
    raw_to = window.get("to")
    events = body.get("events")
    if not isinstance(events, list):
        raise ApiError(422, "validation", "events is required and must be an array")

    try:
        start = metrics.parse_instant(raw_from)
        end = metrics.parse_instant(raw_to)
        if end <= start:
            raise ApiError(422, "validation", "window.to must be after window.from")
        result = metrics.compute(events, start, end)
    except metrics.InvalidLog as exc:
        raise ApiError(422, "malformed_log", str(exc))

    result["spec_version"] = metrics.SPEC_VERSION
    result["window"] = {"from": raw_from, "to": raw_to}
    return JSONResponse(status_code=200, content=result)


@app.get("/dora/ticket-events")
def dora_ticket_events() -> list[dict]:
    stream: list[dict] = []
    for ticket in store.all_tickets():
        for phase, field in TICKET_PHASES:
            at = ticket.get(field)
            if not at:
                continue
            stream.append({
                "ticket_id": ticket["id"],
                "at": at,
                "phase": phase,
                "priority": ticket.get("priority"),
                "state": "new" if phase == "created" else phase,
            })
    stream.sort(key=lambda event: (event["at"], event["ticket_id"]))
    return stream
