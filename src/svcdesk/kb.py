# ai-generated: 85% - opencode drafted the kb-index client and its error mapping from MONITORING-SPEC.md M-02; reviewed by the student
"""kb-index client for svcdesk (Lab 3, MONITORING-SPEC.md M-02).

One upstream call per request: no cache, no retry, a timeout well above the
required 2 s.  Any upstream answer other than 200 - a 503, a timeout, a
connection error - becomes ``upstream_unavailable`` and the endpoint answers
502.
"""

from __future__ import annotations

import os

import httpx

DEFAULT_KB_INDEX_URL = "http://kb-index:8080"
KB_INDEX_URL = os.environ.get("KB_INDEX_URL", DEFAULT_KB_INDEX_URL).rstrip("/")

# M-02 wants at least 2 s; the upstream's slow mode reaches ~250 ms, so 5 s is
# generous enough to never cut a real answer and still finite.
TIMEOUT_SECONDS = 5.0

MAX_Q_LENGTH = 200


class UpstreamUnavailable(Exception):
    """The upstream did not answer 200; the endpoint maps this to 502."""


def new_client() -> httpx.AsyncClient:
    """One pooled client for the process: 64 connections of the load run fit inside."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(TIMEOUT_SECONDS),
        limits=httpx.Limits(max_connections=256, max_keepalive_connections=128),
        follow_redirects=False,
    )


async def search(client: httpx.AsyncClient, q: str) -> list[dict]:
    """GET {KB_INDEX_URL}/search?q=<q> and return the upstream's hits unchanged."""
    try:
        response = await client.get(f"{KB_INDEX_URL}/search", params={"q": q})
    except (httpx.HTTPError, OSError) as exc:  # timeouts, refusals, resets
        raise UpstreamUnavailable(str(exc)) from exc

    if response.status_code != 200:
        raise UpstreamUnavailable(f"kb-index answered {response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise UpstreamUnavailable("kb-index answered a body that is not JSON") from exc

    hits = payload.get("hits") if isinstance(payload, dict) else None
    if not isinstance(hits, list):
        raise UpstreamUnavailable("kb-index answered without a hits list")
    return hits
