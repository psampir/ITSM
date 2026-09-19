# ai-generated: 85% - opencode drafted the wall-clock and business-hours SLA math; reviewed and tested by the student
"""SLA due-instant computation for svcdesk.

Two clocks:
- wall-clock: created_at + target, no pause.
- business-hours: only Monday to Friday, [08:00, 16:00) Europe/Warsaw, DST-aware.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Warsaw")
BUSINESS_OPEN = time(8, 0)
BUSINESS_CLOSE = time(16, 0)

TARGETS: dict[str, tuple[timedelta, timedelta]] = {
    "P1": (timedelta(minutes=15), timedelta(hours=4)),
    "P2": (timedelta(hours=1), timedelta(hours=8)),
    "P3": (timedelta(hours=4), timedelta(hours=24)),
    "P4": (timedelta(hours=8), timedelta(hours=72)),
}


def _opening_on(day: date) -> datetime:
    return datetime.combine(day, BUSINESS_OPEN, tzinfo=TZ)


def _closing_on(day: date) -> datetime:
    return datetime.combine(day, BUSINESS_CLOSE, tzinfo=TZ)


def in_business_window(instant: datetime) -> bool:
    local = instant.astimezone(TZ)
    return local.weekday() < 5 and BUSINESS_OPEN <= local.time() < BUSINESS_CLOSE


def next_opening(instant: datetime) -> datetime:
    local = instant.astimezone(TZ)
    day = local.date()
    candidate = day if local < _opening_on(day) else day + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return _opening_on(candidate)


def add_business_hours(created: datetime, delta: timedelta) -> datetime:
    if delta <= timedelta(0):
        return created.astimezone(timezone.utc)
    cursor = created.astimezone(TZ)
    if not in_business_window(cursor):
        cursor = next_opening(cursor)
    remaining = delta
    while remaining > timedelta(0):
        available = _closing_on(cursor.date()) - cursor
        if remaining <= available:
            cursor = cursor + remaining
            remaining = timedelta(0)
        else:
            remaining -= available
            cursor = next_opening(_closing_on(cursor.date()))
    return cursor.astimezone(timezone.utc)


def add_wall_clock(created: datetime, delta: timedelta) -> datetime:
    return created.astimezone(timezone.utc) + delta


def uses_business_clock(priority: str, c1_wallclock_for_p1: bool) -> bool:
    if priority == "P1" and c1_wallclock_for_p1:
        return False
    return True


def due_instants(priority: str, created: datetime, c1_wallclock_for_p1: bool) -> tuple[datetime, datetime]:
    ack_delta, resolve_delta = TARGETS[priority]
    if uses_business_clock(priority, c1_wallclock_for_p1):
        return add_business_hours(created, ack_delta), add_business_hours(created, resolve_delta)
    return add_wall_clock(created, ack_delta), add_wall_clock(created, resolve_delta)
