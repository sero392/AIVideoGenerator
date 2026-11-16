"""Pure weekly-schedule logic (no DB, no I/O) so it is easy to test.

A window is (day_of_week 0=Mon..6=Sun, "HH:MM" start, "HH:MM" end) in local time.
``end <= start`` means the window runs past midnight into the next day;
``start == end`` means 24 hours.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


@dataclass(frozen=True, slots=True)
class Window:
    day_of_week: int
    start_time: str
    end_time: str


def parse_hhmm(value: str) -> int:
    """'HH:MM' -> minutes since midnight. Raises ValueError for anything else."""
    match = _HHMM.match(value)
    if not match:
        raise ValueError("Saat SS:DD biçiminde olmalıdır (ör. 20:30).")
    return int(match.group(1)) * 60 + int(match.group(2))


def _bounds(window: Window, day_start: datetime) -> tuple[datetime, datetime]:
    """Concrete [start, end) for the occurrence of ``window`` that starts on ``day_start``'s date."""
    start = day_start + timedelta(minutes=parse_hhmm(window.start_time))
    end_min = parse_hhmm(window.end_time)
    end = day_start + timedelta(minutes=end_min)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def _occurrences(windows: Iterable[Window], now: datetime, days_back: int = 1, days_ahead: int = 8):  # type: ignore[no-untyped-def]
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for offset in range(-days_back, days_ahead):
        day = midnight + timedelta(days=offset)
        for w in windows:
            if day.weekday() == w.day_of_week:
                yield _bounds(w, day)


def active_window_end(windows: Iterable[Window], now: datetime) -> datetime | None:
    """End of the window containing ``now`` (latest end if several overlap), else None."""
    ends = [end for start, end in _occurrences(list(windows), now) if start <= now < end]
    return max(ends) if ends else None


def is_within_schedule(windows: Iterable[Window], now: datetime) -> bool:
    return active_window_end(windows, now) is not None


def next_window_start(windows: Iterable[Window], now: datetime) -> datetime | None:
    starts = [start for start, _ in _occurrences(list(windows), now, days_back=0) if start > now]
    return min(starts) if starts else None
