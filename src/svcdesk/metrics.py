# ai-generated: 85% - opencode drafted the DORA metric engine from METRIC-SPEC.md; reviewed and tested by the student
"""DORA delivery metrics for svcdesk (Lab 2).

Implements METRIC-SPEC.md rules R-01..R-17: event-log validation, the observation
window, change identity through transitive reverts, the five metrics, the six
edge-case anomalies and the two ground-truth numbers. Pure functions only - the
endpoint is a stateless function of its request body.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Any

SPEC_VERSION = "1.0.0"

_INSTANT_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$"
)
_OUTCOMES = {"success", "failure"}
_PHASES = {"opened", "resolved"}


class InvalidLog(Exception):
    """Raised when an event log is not well formed (METRIC-SPEC.md section 1)."""


def parse_instant(value: Any) -> datetime:
    if not isinstance(value, str) or not _INSTANT_RE.match(value):
        raise InvalidLog(f"{value!r} is not an RFC 3339 instant")
    text = value[:-1] + "+00:00" if value[-1] in "Zz" else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise InvalidLog(f"{value!r} is not an RFC 3339 instant") from exc
    if parsed.tzinfo is None:
        raise InvalidLog(f"{value!r} has no UTC offset")
    return parsed.astimezone(timezone.utc)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidLog(message)


def _plain_string(value: Any, field: str) -> str:
    _require(isinstance(value, str) and value != "", f"{field} must be a non-empty string")
    return value


def _optional_string(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _plain_string(value, field)


def _dedupe(events: list[Any]) -> list[dict]:
    """R-05: an event_id seen before is ignored, and that is not an error."""
    seen: set[str] = set()
    unique: list[dict] = []
    for index, event in enumerate(events):
        _require(isinstance(event, dict), f"event {index} is not an object")
        event_id = event.get("event_id")
        _require(isinstance(event_id, str) and 1 <= len(event_id) <= 64,
                 f"event {index} has an invalid event_id")
        if event_id in seen:
            continue
        seen.add(event_id)
        unique.append(event)
    return unique


def _parse_events(events: list[dict]) -> tuple[dict, list, dict]:
    commits: dict[str, dict] = {}
    deployments: list[dict] = []
    incidents: dict[str, dict] = {}

    for event in events:
        kind = event.get("type")
        at = parse_instant(event.get("at"))

        if kind == "commit":
            sha = _plain_string(event.get("sha"), "sha")
            _require(sha not in commits, f"duplicate sha {sha}")
            branch = _plain_string(event.get("branch"), "branch")
            reverts = _optional_string(event.get("reverts"), "reverts")
            change_id = _optional_string(event.get("change_id"), "change_id")
            if reverts is None:
                _require(change_id is not None, f"commit {sha} has no change_id and no reverts")
            else:
                _require(change_id is None, f"commit {sha} both reverts and carries a change_id")
            commits[sha] = {
                "sha": sha, "at": at, "branch": branch,
                "change_id": change_id, "reverts": reverts,
            }

        elif kind == "deployment":
            deployment_id = _plain_string(event.get("deployment_id"), "deployment_id")
            environment = _plain_string(event.get("environment"), "environment")
            outcome = event.get("outcome")
            _require(outcome in _OUTCOMES, f"deployment {deployment_id} has an invalid outcome")
            carried = event.get("commits")
            if not isinstance(carried, list) or not all(isinstance(s, str) for s in carried):
                raise InvalidLog(f"deployment {deployment_id} has invalid commits")
            unplanned = event.get("unplanned")
            _require(isinstance(unplanned, bool), f"deployment {deployment_id} has invalid unplanned")
            caused_by = _optional_string(event.get("caused_by"), "caused_by")
            deployments.append({
                "deployment_id": deployment_id, "at": at, "environment": environment,
                "outcome": outcome, "commits": list(carried),
                "unplanned": unplanned, "caused_by": caused_by,
            })

        elif kind == "incident":
            incident_id = _plain_string(event.get("incident_id"), "incident_id")
            phase = event.get("phase")
            _require(phase in _PHASES, f"incident {incident_id} has an invalid phase")
            covered = event.get("deployments")
            if not isinstance(covered, list) or not all(isinstance(s, str) for s in covered):
                raise InvalidLog(f"incident {incident_id} has invalid deployments")
            record = incidents.setdefault(
                incident_id, {"opened": None, "resolved": None, "deployments": set()}
            )
            slot = "opened" if phase == "opened" else "resolved"
            if record[slot] is None or at < record[slot]:
                record[slot] = at
            record["deployments"].update(covered)

        else:
            raise InvalidLog(f"unknown event type {kind!r}")

    _check_references(commits, deployments, incidents)
    return commits, deployments, incidents


def _check_references(commits: dict, deployments: list, incidents: dict) -> None:
    shas = set(commits)
    deployment_ids = {d["deployment_id"] for d in deployments}
    incident_ids = set(incidents)

    for commit in commits.values():
        if commit["reverts"] is not None:
            _require(commit["reverts"] in shas, f"reverts names unknown sha {commit['reverts']}")
    for deployment in deployments:
        for sha in deployment["commits"]:
            _require(sha in shas, f"deployment {deployment['deployment_id']} names unknown sha {sha}")
        if deployment["caused_by"] is not None:
            _require(deployment["caused_by"] in incident_ids,
                     f"deployment {deployment['deployment_id']} names unknown incident")
    for incident_id, incident in incidents.items():
        for deployment_id in incident["deployments"]:
            _require(deployment_id in deployment_ids,
                     f"incident {incident_id} names unknown deployment {deployment_id}")
        if incident["resolved"] is not None:
            _require(incident["opened"] is not None,
                     f"incident {incident_id} resolved but never opened")


def _resolve_changes(commits: dict) -> dict[str, str]:
    """R-06: a revert inherits, transitively, the change_id of the commit it reverts."""
    change_of: dict[str, str] = {}

    for start in commits:
        if start in change_of:
            continue
        path: list[str] = []
        current = start
        seen: set[str] = set()
        while commits[current]["reverts"] is not None:
            if current in seen:
                raise InvalidLog(f"revert cycle at {current}")
            seen.add(current)
            path.append(current)
            current = commits[current]["reverts"]
        change_id = commits[current]["change_id"]
        for sha in (*path, current):
            change_of[sha] = change_id

    return change_of


def _microseconds(delta: timedelta) -> int:
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def _round_seconds(value: Fraction) -> int:
    seconds = Fraction(value, 1_000_000)
    return int((seconds + Fraction(1, 2)).__floor__())


def _median_seconds(samples_us: list[int]) -> int | None:
    if not samples_us:
        return None
    ordered = sorted(samples_us)
    count = len(ordered)
    if count % 2:
        middle = Fraction(ordered[count // 2])
    else:
        middle = Fraction(ordered[count // 2 - 1] + ordered[count // 2], 2)
    return _round_seconds(middle)


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    value = (Decimal(numerator) / Decimal(denominator)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    return float(value)


def _frequency(count: int, window_us: int) -> float:
    days = Decimal(window_us) / Decimal(86_400_000_000)
    value = (Decimal(count) / days).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return float(value)


def compute(events: list[Any], window_from: datetime, window_to: datetime) -> dict:
    """Apply METRIC-SPEC.md to a deduplicated, validated event log."""
    unique = _dedupe(events)
    commits, deployments, incidents = _parse_events(unique)
    change_of = _resolve_changes(commits)

    # R-07: a change's first commit instant, anywhere in the log.
    first_commit: dict[str, datetime] = {}
    for commit in commits.values():
        change_id = change_of[commit["sha"]]
        moment = commit["at"]
        if change_id not in first_commit or moment < first_commit[change_id]:
            first_commit[change_id] = moment

    # R-01/R-02: production deployments inside the half-open window.
    in_window = [
        d for d in deployments
        if d["environment"] == "production" and window_from <= d["at"] < window_to
    ]
    in_window.sort(key=lambda d: (d["at"], d["deployment_id"]))

    successful = [d for d in in_window if d["outcome"] == "success"]
    failed = [d for d in in_window if d["outcome"] == "failure"]

    # R-08: one pair per sha, at that commit's first successful in-window deployment.
    first_success: dict[str, dict] = {}
    for deployment in in_window:
        if deployment["outcome"] != "success":
            continue
        for sha in deployment["commits"]:
            first_success.setdefault(sha, deployment)
    lead_samples: list[int] = []
    negative_pairs = 0
    for sha, deployment in first_success.items():
        delta = _microseconds(deployment["at"] - commits[sha]["at"])
        if delta < 0:
            negative_pairs += 1
            delta = 0
        lead_samples.append(delta)

    # R-09 (E3): distinct off-main shas carried by any in-window production deployment.
    off_main = {
        sha
        for deployment in in_window
        for sha in deployment["commits"]
        if commits[sha]["branch"] != "main"
    }

    # R-10 (E4): production deployments in the window with no linked commits.
    without_commits = sum(1 for d in in_window if not d["commits"])

    # R-12 (E5): recovery is per failed deployment, via its earliest covering incident.
    recovered_samples: list[int] = []
    open_failures = 0
    for deployment in failed:
        covers = sorted(
            (incident["opened"], incident_id)
            for incident_id, incident in incidents.items()
            if incident["opened"] is not None
            and deployment["deployment_id"] in incident["deployments"]
        )
        if not covers:
            open_failures += 1
            continue
        covering = incidents[covers[0][1]]
        if covering["resolved"] is None:
            open_failures += 1
            continue
        recovered_samples.append(max(0, _microseconds(covering["resolved"] - deployment["at"])))

    # R-13 (E6): overlapping-incident pairs, computed on intervals, never merged.
    intervals = [
        (incident["opened"], incident["resolved"] or window_to)
        for incident in incidents.values()
        if incident["opened"] is not None
    ]
    overlapping_pairs = 0
    for left in range(len(intervals)):
        for right in range(left + 1, len(intervals)):
            first, second = intervals[left], intervals[right]
            if first[0] < second[1] and second[0] < first[1]:
                overlapping_pairs += 1

    # R-15: unplanned deployments with a root cause.
    rework = [d for d in in_window if d["unplanned"] and d["caused_by"] is not None]

    # R-16/R-17: ground truth, measured over changes, not pairs.
    delivered: dict[str, datetime] = {}
    for deployment in in_window:
        if deployment["outcome"] != "success":
            continue
        for sha in deployment["commits"]:
            delivered.setdefault(change_of[sha], deployment["at"])
    true_lead_samples = [
        max(0, _microseconds(deployment_at - first_commit[change_id]))
        for change_id, deployment_at in delivered.items()
    ]

    window_us = _microseconds(window_to - window_from)

    return {
        "deployment_frequency_per_day": _frequency(len(in_window), window_us),
        "change_lead_time_seconds_p50": _median_seconds(lead_samples),
        "failed_deployment_recovery_time_seconds_p50": _median_seconds(recovered_samples),
        "change_fail_rate": _rate(len(failed), len(in_window)),
        "deployment_rework_rate": _rate(len(rework), len(in_window)),
        "counts": {
            "deployments": len(in_window),
            "successful_deployments": len(successful),
            "failed_deployments": len(failed),
            "recovered_failures": len(recovered_samples),
            "open_failures": open_failures,
            "rework_deployments": len(rework),
            "lead_time_pairs": len(lead_samples),
            "changes": len(set(change_of.values())),
        },
        "anomalies": {
            "negative_lead_time_pairs": negative_pairs,
            "deployments_without_commits": without_commits,
            "commits_never_on_main": len(off_main),
            "revert_chains_collapsed": sum(1 for c in commits.values() if c["reverts"] is not None),
            "overlapping_incident_pairs": overlapping_pairs,
        },
        "ground_truth": {
            "changes_delivered": len(delivered),
            "true_change_lead_time_seconds_p50": _median_seconds(true_lead_samples),
        },
    }
