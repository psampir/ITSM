# ai-generated: 70% - written with an assistant from the module's docstrings; every boundary was re-checked by hand against the specification
"""Tests for slaclock.py (Lab 5, Stretch 1, CI-SPEC.md P-29).

Only pytest and the standard library; nothing at import time calls the module, so a mutant that raises
inside a function is a test failure and not a collection error. The docstrings of slaclock are the
specification: every assertion below pins a boundary they state.
"""

from datetime import datetime

import pytest

import slaclock


# --- priority_of -----------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("impact", "urgency", "expected"),
    [
        (1, 1, "P1"),
        (1, 2, "P2"),
        (2, 1, "P2"),
        (1, 3, "P3"),
        (2, 2, "P3"),
        (3, 1, "P3"),
        (2, 3, "P4"),
        (3, 2, "P4"),
        (3, 3, "P4"),
    ],
)
def test_priority_matrix(impact, urgency, expected):
    assert slaclock.priority_of(impact, urgency) == expected


@pytest.mark.parametrize(
    ("impact", "urgency", "expected"),
    [
        (1, 1, "P1"),
        (1, 2, "P2"),
        (2, 1, "P2"),
        (1, 3, "P2"),
        (2, 2, "P2"),
        (3, 1, "P2"),
        (2, 3, "P2"),
        (3, 2, "P2"),
        (3, 3, "P2"),
    ],
)
def test_vip_is_never_below_p2(impact, urgency, expected):
    assert slaclock.priority_of(impact, urgency, vip=True) == expected


def test_vip_keyword_and_p1_untouched():
    assert slaclock.priority_of(1, 1, vip=True) == "P1"
    assert slaclock.priority_of(impact=1, urgency=2, vip=False) == "P2"


@pytest.mark.parametrize("bad", [0, 4, -1, 2.0, 1.5, True, False, "1", None, (1,), [1]])
def test_priority_rejects_anything_but_an_int_from_1_to_3(bad):
    with pytest.raises(ValueError):
        slaclock.priority_of(bad, 1)
    with pytest.raises(ValueError):
        slaclock.priority_of(1, bad)


def test_priority_accepts_both_boundaries():
    assert slaclock.priority_of(1, 1) == "P1"
    assert slaclock.priority_of(3, 3) == "P4"


# --- targets ---------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("priority", "expected"),
    [("P1", (15, 240)), ("P2", (60, 480)), ("P3", (240, 1440)), ("P4", (480, 4320))],
)
def test_targets_of_every_priority(priority, expected):
    assert slaclock.targets(priority) == expected
    response, resolution = slaclock.targets(priority)
    assert (response, resolution) == expected


@pytest.mark.parametrize("bad", ["p1", " P1", "P1 ", "P5", "P0", "", "1", None, 1])
def test_targets_is_an_exact_lookup(bad):
    with pytest.raises(ValueError):
        slaclock.targets(bad)


# --- sla_state -------------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("elapsed", "target", "expected"),
    [
        (0, 15, "ok"),
        (11, 15, "ok"),
        (12, 15, "warning"),
        (13, 15, "warning"),
        (15, 15, "warning"),
        (16, 15, "breached"),
        (1, 1, "warning"),
        (2, 1, "breached"),
        (0, 1, "ok"),
        (3, 4, "warning"),
        (2, 4, "ok"),
        (4, 4, "warning"),
        (5, 4, "breached"),
        (74, 100, "ok"),
        (75, 100, "warning"),
        (100, 100, "warning"),
        (101, 100, "breached"),
        (0, 4320, "ok"),
        (3239, 4320, "ok"),
        (3240, 4320, "warning"),
        (4320, 4320, "warning"),
        (4321, 4320, "breached"),
    ],
)
def test_sla_state_boundaries(elapsed, target, expected):
    assert slaclock.sla_state(elapsed, target) == expected


@pytest.mark.parametrize(("elapsed", "target"), [(-1, 10), (-100, 10), (0, 0), (5, 0), (0, -5), (-1, -1)])
def test_sla_state_rejects_negative_inputs(elapsed, target):
    with pytest.raises(ValueError):
        slaclock.sla_state(elapsed, target)


# --- is_business_time ------------------------------------------------------------------------------

def test_business_time_window_on_a_weekday():
    monday = datetime(2026, 11, 16, 0, 0)  # a Monday
    assert monday.weekday() == 0
    assert slaclock.is_business_time(monday.replace(hour=7, minute=59)) is False
    assert slaclock.is_business_time(monday.replace(hour=8, minute=0)) is True
    assert slaclock.is_business_time(monday.replace(hour=12, minute=0)) is True
    assert slaclock.is_business_time(monday.replace(hour=15, minute=59)) is True
    assert slaclock.is_business_time(monday.replace(hour=16, minute=0)) is False
    assert slaclock.is_business_time(monday.replace(hour=23, minute=59)) is False
    assert slaclock.is_business_time(monday.replace(hour=0, minute=0)) is False


@pytest.mark.parametrize("day", [14, 15])  # Saturday, Sunday in November 2026
def test_weekend_is_never_business_time(day):
    moment = datetime(2026, 11, day, 10, 0)
    assert moment.weekday() >= 5
    assert slaclock.is_business_time(moment) is False


def test_friday_and_monday_are_business_days():
    assert slaclock.is_business_time(datetime(2026, 11, 13, 8, 0)) is True  # Friday
    assert slaclock.is_business_time(datetime(2026, 11, 16, 8, 0)) is True  # Monday


def test_seconds_are_ignored_by_business_time():
    assert slaclock.is_business_time(datetime(2026, 11, 16, 8, 0, 59)) is True
    assert slaclock.is_business_time(datetime(2026, 11, 16, 15, 59, 59)) is True


# --- add_business_minutes --------------------------------------------------------------------------

def test_zero_minutes_inside_business_hours_gives_the_start():
    start = datetime(2026, 11, 16, 9, 30)
    assert slaclock.add_business_minutes(start, 0) == start


def test_zero_minutes_truncates_seconds_of_the_start():
    start = datetime(2026, 11, 16, 9, 30, 45, 123)
    assert slaclock.add_business_minutes(start, 0) == datetime(2026, 11, 16, 9, 30)


def test_zero_minutes_before_opening_moves_to_the_same_day():
    assert slaclock.add_business_minutes(datetime(2026, 11, 16, 7, 0), 0) == datetime(2026, 11, 16, 8, 0)


def test_zero_minutes_after_closing_moves_to_the_next_business_day():
    friday = datetime(2026, 11, 13, 17, 0)
    assert slaclock.add_business_minutes(friday, 0) == datetime(2026, 11, 16, 8, 0)


def test_zero_minutes_on_a_weekend_moves_to_monday():
    assert slaclock.add_business_minutes(datetime(2026, 11, 14, 10, 0), 0) == datetime(2026, 11, 16, 8, 0)
    assert slaclock.add_business_minutes(datetime(2026, 11, 15, 10, 0), 0) == datetime(2026, 11, 16, 8, 0)


def test_minutes_ending_exactly_at_closing_stay_on_the_day():
    monday = datetime(2026, 11, 16, 8, 0)
    assert slaclock.add_business_minutes(monday, 480) == datetime(2026, 11, 16, 16, 0)
    assert slaclock.add_business_minutes(datetime(2026, 11, 16, 9, 0), 420) == datetime(2026, 11, 16, 16, 0)


def test_one_minute_more_than_the_day_spills_to_the_next_opening():
    monday_9 = datetime(2026, 11, 16, 9, 0)
    assert slaclock.add_business_minutes(monday_9, 421) == datetime(2026, 11, 17, 8, 1)
    assert slaclock.add_business_minutes(datetime(2026, 11, 16, 15, 0), 61) == datetime(2026, 11, 17, 8, 1)


def test_minutes_cross_the_weekend():
    friday_15 = datetime(2026, 11, 13, 15, 0)
    assert slaclock.add_business_minutes(friday_15, 60) == datetime(2026, 11, 13, 16, 0)
    assert slaclock.add_business_minutes(friday_15, 61) == datetime(2026, 11, 16, 8, 1)
    assert slaclock.add_business_minutes(friday_15, 120) == datetime(2026, 11, 16, 9, 0)


def test_negative_minutes_raise():
    with pytest.raises(ValueError):
        slaclock.add_business_minutes(datetime(2026, 11, 16, 9, 0), -1)


def test_a_due_date_beyond_the_calendar_cap_raises():
    with pytest.raises(ValueError):
        slaclock.add_business_minutes(datetime(2026, 1, 5, 8, 0), 200000)


# --- business_minutes_between ----------------------------------------------------------------------

def test_empty_interval_is_zero():
    moment = datetime(2026, 11, 16, 9, 0)
    assert slaclock.business_minutes_between(moment, moment) == 0


def test_end_before_start_raises():
    with pytest.raises(ValueError):
        slaclock.business_minutes_between(datetime(2026, 11, 16, 10, 0), datetime(2026, 11, 16, 9, 0))


def test_more_than_the_calendar_cap_apart_raises():
    with pytest.raises(ValueError):
        slaclock.business_minutes_between(datetime(2026, 1, 5, 8, 0), datetime(2027, 1, 7, 8, 0))


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (datetime(2026, 11, 16, 8, 0), datetime(2026, 11, 16, 16, 0), 480),
        (datetime(2026, 11, 16, 7, 0), datetime(2026, 11, 16, 8, 30), 30),
        (datetime(2026, 11, 16, 15, 0), datetime(2026, 11, 16, 17, 0), 60),
        (datetime(2026, 11, 16, 17, 0), datetime(2026, 11, 16, 23, 0), 0),
        (datetime(2026, 11, 16, 0, 0), datetime(2026, 11, 16, 0, 30), 0),
        (datetime(2026, 11, 14, 9, 0), datetime(2026, 11, 15, 12, 0), 0),
        (datetime(2026, 11, 13, 15, 0), datetime(2026, 11, 16, 9, 0), 120),
        (datetime(2026, 11, 16, 8, 0), datetime(2026, 11, 16, 8, 1), 1),
        (datetime(2026, 11, 16, 8, 30, 45), datetime(2026, 11, 16, 9, 0, 59), 30),
        (datetime(2026, 11, 20, 12, 0), datetime(2026, 11, 23, 12, 0), 480),
    ],
)
def test_business_minutes_between(start, end, expected):
    assert slaclock.business_minutes_between(start, end) == expected


@pytest.mark.parametrize(
    ("start", "minutes"),
    [
        (datetime(2026, 11, 16, 8, 0), 0),
        (datetime(2026, 11, 16, 8, 0), 1),
        (datetime(2026, 11, 16, 9, 0), 420),
        (datetime(2026, 11, 16, 9, 0), 421),
        (datetime(2026, 11, 16, 15, 30), 45),
        (datetime(2026, 11, 16, 7, 0), 1),
        (datetime(2026, 11, 16, 17, 0), 1),
        (datetime(2026, 11, 13, 15, 0), 61),
        (datetime(2026, 11, 14, 12, 0), 30),
        (datetime(2026, 11, 16, 8, 0), 480),
        (datetime(2026, 11, 16, 8, 0), 2400),
    ],
)
def test_the_two_business_functions_agree(start, minutes):
    due = slaclock.add_business_minutes(start, minutes)
    assert slaclock.business_minutes_between(start, due) == minutes


# --- escalation_tier -------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("priority", "breached", "reopens", "expected"),
    [
        ("P1", False, 0, 1),
        ("P2", False, 0, 1),
        ("P3", False, 0, 0),
        ("P4", False, 0, 0),
        ("P1", True, 0, 3),
        ("P2", True, 0, 2),
        ("P3", True, 0, 1),
        ("P4", True, 0, 1),
        ("P1", False, 2, 2),
        ("P2", False, 2, 2),
        ("P3", False, 2, 1),
        ("P4", False, 2, 1),
        ("P1", False, 1, 1),
        ("P3", False, 1, 0),
        ("P1", True, 2, 3),
        ("P2", True, 2, 3),
        ("P3", True, 2, 2),
        ("P4", True, 5, 2),
    ],
)
def test_escalation_tiers(priority, breached, reopens, expected):
    assert slaclock.escalation_tier(priority, breached, reopens) == expected


@pytest.mark.parametrize("bad", ["p1", "P5", "", None])
def test_escalation_rejects_an_unknown_priority(bad):
    with pytest.raises(ValueError):
        slaclock.escalation_tier(bad, False, 0)


def test_escalation_rejects_negative_reopens():
    with pytest.raises(ValueError):
        slaclock.escalation_tier("P1", False, -1)


# --- parse_duration --------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("90m", 90),
        ("4h", 240),
        ("1h30m", 90),
        ("2d", 2880),
        ("1d4h", 1680),
        ("1d0h5m", 1445),
        ("60m", 60),
        ("0h60m", 60),
        ("0d1h", 60),
        ("1d0h0m", 1440),
        (" 90m ", 90),
        ("\t4h\n", 240),
        ("1h59m", 119),
        ("01h05m", 65),
        ("25h", 1500),
        ("1m", 1),
    ],
)
def test_parse_duration_accepts(text, expected):
    assert slaclock.parse_duration(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "0m",
        "0d",
        "0h",
        "0d0h0m",
        "1.5h",
        "30m1h",
        "-5m",
        "1 h",
        "1H",
        "1h 30m",
        "1h30",
        "1d1d",
        "d",
        "m",
        "1h60m",
        "1d60m",
        "2d1h60m",
        "5",
        "m5",
        "+5m",
    ],
)
def test_parse_duration_rejects(text):
    with pytest.raises(ValueError):
        slaclock.parse_duration(text)


# --- boundaries beyond the obvious ones (found with mutmut) ----------------------------------------

def test_business_window_is_not_confused_by_half_hours():
    # hour*60 - minute would put 08:30 at 07:30 and 16:30 at 15:30
    monday = datetime(2026, 11, 16, 8, 30)
    assert slaclock.is_business_time(monday) is True
    assert slaclock.is_business_time(monday.replace(hour=16, minute=30)) is False


def test_a_start_at_the_closing_minute_moves_to_the_next_day():
    monday_closing = datetime(2026, 11, 16, 16, 0)
    assert slaclock.add_business_minutes(monday_closing, 0) == datetime(2026, 11, 17, 8, 0)


def test_the_last_minute_of_the_day_is_usable():
    assert slaclock.add_business_minutes(datetime(2026, 11, 16, 15, 59), 1) == datetime(2026, 11, 16, 16, 0)


def test_between_ignores_microseconds_of_the_start():
    start = datetime(2026, 11, 16, 8, 0, 0, 500000)
    end = datetime(2026, 11, 16, 8, 1, 0)
    assert slaclock.business_minutes_between(start, end) == 1


def test_between_ignores_seconds_below_a_whole_minute():
    assert slaclock.business_minutes_between(
        datetime(2026, 11, 16, 8, 0, 0), datetime(2026, 11, 16, 8, 0, 59)
    ) == 0


def test_the_calendar_cap_is_inclusive_and_the_next_day_is_not():
    # 2026-01-05 is a Monday; offsets 0..366 hold 263 business days of 480 minutes each.
    start = datetime(2026, 1, 5, 8, 0)
    budget = 263 * 480
    assert slaclock.add_business_minutes(start, budget) == datetime(2027, 1, 6, 16, 0)
    with pytest.raises(ValueError):
        slaclock.add_business_minutes(start, budget + 1)
    assert slaclock.business_minutes_between(start, datetime(2027, 1, 6, 16, 0)) == budget


def test_business_minutes_are_integers():
    # the functions are annotated -> int; a float would break arithmetic on the clock
    assert isinstance(slaclock.business_minutes_between(
        datetime(2026, 11, 16, 8, 0), datetime(2026, 11, 16, 9, 0)), int)
    assert isinstance(slaclock.business_minutes_between(
        datetime(2026, 11, 16, 8, 0), datetime(2026, 11, 16, 8, 1)), int)


def test_a_weekend_start_before_opening_waits_for_monday():
    assert slaclock.add_business_minutes(datetime(2026, 11, 14, 7, 0), 1) == datetime(2026, 11, 16, 8, 1)
    assert slaclock.add_business_minutes(datetime(2026, 11, 15, 23, 0), 0) == datetime(2026, 11, 16, 8, 0)
