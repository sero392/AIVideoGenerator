from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.streamer.schedule import (
    Window,
    active_window_end,
    is_within_schedule,
    next_window_start,
    parse_hhmm,
)

TZ = ZoneInfo("Europe/Istanbul")
MON, TUE, SUN = 0, 1, 6


def at(day: int, hhmm: str) -> datetime:
    """A local datetime in the week of Mon 2026-11-16."""
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, 11, 16 + day, h, m, tzinfo=TZ)


def test_parse_hhmm() -> None:
    assert parse_hhmm("00:00") == 0
    assert parse_hhmm("23:59") == 23 * 60 + 59
    for bad in ("24:00", "7:00", "12:60", "ab:cd", ""):
        with pytest.raises(ValueError):
            parse_hhmm(bad)


def test_same_day_window() -> None:
    w = [Window(MON, "20:00", "23:00")]
    assert not is_within_schedule(w, at(MON, "19:59"))
    assert is_within_schedule(w, at(MON, "20:00"))
    assert not is_within_schedule(w, at(MON, "23:00"))  # end is exclusive
    assert not is_within_schedule(w, at(TUE, "21:00"))


def test_window_crossing_midnight() -> None:
    w = [Window(MON, "22:00", "02:00")]
    assert is_within_schedule(w, at(MON, "23:30"))
    assert is_within_schedule(w, at(TUE, "01:59"))
    assert not is_within_schedule(w, at(TUE, "02:00"))
    assert active_window_end(w, at(MON, "23:00")) == at(TUE, "02:00")


def test_sunday_night_wraps_to_monday() -> None:
    w = [Window(SUN, "23:00", "01:00")]
    assert is_within_schedule(w, at(MON, "00:30"))  # Monday morning belongs to last Sunday's window


def test_full_day_window() -> None:
    w = [Window(MON, "00:00", "00:00")]
    assert is_within_schedule(w, at(MON, "00:00"))
    assert is_within_schedule(w, at(MON, "23:59"))
    assert not is_within_schedule(w, at(TUE, "00:00"))


def test_next_window_start_and_overlap() -> None:
    w = [Window(MON, "20:00", "22:00"), Window(MON, "21:00", "23:30"), Window(TUE, "08:00", "09:00")]
    assert next_window_start(w, at(MON, "10:00")) == at(MON, "20:00")
    assert next_window_start(w, at(MON, "20:30")) == at(MON, "21:00")
    assert active_window_end(w, at(MON, "21:30")) == at(MON, "23:30")  # latest end of overlapping windows
    assert next_window_start(w, at(TUE, "10:00")) == at(MON, "20:00").replace(day=23)  # next week
    assert next_window_start([], at(MON, "10:00")) is None
    assert not is_within_schedule([], at(MON, "10:00"))
