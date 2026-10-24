# ai-generated: 80% - opencode drafted the ASGI middleware, the label policy and the /metrics response from MONITORING-SPEC.md M-03..M-07; reviewed by the student
"""Request instrumentation for svcdesk (Lab 3, MONITORING-SPEC.md M-03 to M-07).

One histogram - ``http_server_request_duration_seconds``, in seconds - observes
every request exactly once, with three labels:

* ``http_request_method`` - the HTTP method,
* ``http_route`` - the route template (``/tickets/{ticket_id}``), never a raw
  path, an id or a query string; one constant value (``unmatched``) for every
  request that matches no route,
* ``http_response_status_code`` - the numeric status as a string.

The label policy is the cardinality budget of M-07: a random id in a label
would add one series per request, and the checker sends 1,000 of them.
"""

from __future__ import annotations

import time

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Histogram, generate_latest
from starlette.routing import Match
from starlette.types import ASGIApp, Message, Receive, Scope, Send

UNMATCHED = "unmatched"

# The ladder this service exposes, designed from the M-08 measurement of
# 24 October 2026 (q = 116.0 ms).  The bin that resolves the p99 spans
# 0.095-0.130 s in 5 ms steps, so a +/-10 % band around q (104-128 ms) is
# resolved with buckets ~4 % of q wide; the coarse ends cover the median
# (18 ms) and the far tail.  29 finite boundaries, one of them (0.125 s) is
# the latency SLI's threshold (M-13).
LADDER: tuple[float, ...] = (
    0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04,
    0.05, 0.06, 0.07, 0.08, 0.09, 0.095,
    0.1, 0.105, 0.11, 0.115, 0.12, 0.125, 0.13, 0.135, 0.14, 0.15, 0.16,
    0.18, 0.2, 0.3, 0.5,
)

REQUEST_DURATION = Histogram(
    "http_server_request_duration_seconds",
    "Duration of every HTTP request the service answers, in seconds.",
    labelnames=("http_request_method", "http_route", "http_response_status_code"),
    buckets=LADDER,
)


def route_template(scope: Scope) -> str:
    """Return the matched route's template, or UNMATCHED when nothing matched.

    Starlette records the matched route in ``scope["route"]``; the fallback
    matches the scope again for the paths where it does not (405, 404).
    """
    route = scope.get("route")
    template = getattr(route, "path", None)
    if template:
        return template

    app = scope.get("app")
    router = getattr(app, "router", None)
    for candidate in getattr(router, "routes", ()):
        match, _child = candidate.matches(scope)
        if match == Match.FULL:
            return getattr(candidate, "path", None) or UNMATCHED
    return UNMATCHED


class RequestMetricsMiddleware:
    """Pure ASGI middleware: one observation per answered request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == "/metrics":
            await self.app(scope, receive, send)
            return

        started = time.perf_counter()
        status = {"code": 500}

        async def send_with_status(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            elapsed = time.perf_counter() - started
            REQUEST_DURATION.labels(
                scope.get("method", "GET"),
                route_template(scope),
                str(status["code"]),
            ).observe(elapsed)


def render() -> tuple[bytes, str]:
    """The Prometheus text exposition, with the text/plain content type M-03 wants."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
