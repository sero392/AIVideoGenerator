"""Tracking cycle + API with a fake adapter (no network)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import get_session_factory
from app.main import app
from app.models import StreamEvent, StreamEventType, StreamPlatform, StreamStatus, Streamer, TrackingState, TrackingWindow
from app.services.streamer.platforms import ChannelRef, LiveStatus, PlatformAdapter, PlatformError
from app.services.streamer.tracking_service import Tracker, get_tracker

# Monday 2026-11-16 20:30 in Europe/Istanbul (UTC+3)
MON_2030 = datetime(2026, 11, 16, 17, 30, tzinfo=timezone.utc)


class FakeAdapter(PlatformAdapter):
    platform = StreamPlatform.TWITCH
    required_settings = ("TWITCH_CLIENT_ID",)

    def __init__(self, configured: bool = True) -> None:
        super().__init__(poll_interval_seconds=120)
        self.configured = configured
        self.live: set[int] = set()
        self.fail: PlatformError | None = None
        self.calls: list[list[int]] = []

    def is_configured(self) -> bool:
        return self.configured

    async def check(self, channels: list[ChannelRef]):  # type: ignore[no-untyped-def]
        self.calls.append([c.streamer_id for c in channels])
        if self.fail:
            raise self.fail
        return {
            c.streamer_id: LiveStatus(is_live=c.streamer_id in self.live, title="T" if c.streamer_id in self.live else None,
                                      resolved_channel_id="tw-1")
            for c in channels
        }


@pytest.fixture()
def fake() -> FakeAdapter:
    return FakeAdapter()


@pytest.fixture()
def tracker(fake: FakeAdapter) -> Tracker:
    return Tracker(get_settings(), get_session_factory(), adapters={StreamPlatform.TWITCH: fake})


@pytest.fixture()
def api(client: TestClient, tracker: Tracker) -> Iterator[TestClient]:
    app.dependency_overrides[get_tracker] = lambda: tracker
    yield client
    app.dependency_overrides.pop(get_tracker, None)


def _streamer(db: Session, name: str = "A", platform: StreamPlatform = StreamPlatform.TWITCH, *, active: bool = True,
              windows: list[tuple[int, str, str]] | None = None) -> Streamer:
    host = {"twitch": "twitch.tv", "kick": "kick.com", "youtube": "youtube.com", "other": "example.org"}[platform.value]
    s = Streamer(name=name, platform=platform, channel_url=f"https://{host}/{name.lower()}", is_active=active)
    s.tracking_windows = [TrackingWindow(day_of_week=d, start_time=a, end_time=b) for d, a, b in (windows or [(0, "20:00", "23:00")])]
    db.add(s)
    db.commit()
    return s


def _status(db: Session, streamer_id: int) -> StreamStatus:
    db.expire_all()
    return db.get(StreamStatus, streamer_id)  # type: ignore[return-value]


# --- cycle --------------------------------------------------------------------
async def test_cycle_states(db: Session, tracker: Tracker, fake: FakeAdapter) -> None:
    in_window = _streamer(db, "In")
    outside = _streamer(db, "Out", windows=[(2, "10:00", "11:00")])
    inactive = _streamer(db, "Off", active=False)
    other = _streamer(db, "Oth", StreamPlatform.OTHER)
    no_adapter_yet = _streamer(db, "Yt", StreamPlatform.YOUTUBE)

    await tracker.run_cycle(now=MON_2030)

    assert fake.calls == [[in_window.id]]
    assert _status(db, in_window.id).state is TrackingState.OFFLINE
    assert _status(db, outside.id).state is TrackingState.OUTSIDE_SCHEDULE
    assert _status(db, inactive.id).state is TrackingState.INACTIVE
    assert _status(db, other.id).state is TrackingState.UNSUPPORTED
    assert _status(db, no_adapter_yet.id).state is TrackingState.UNSUPPORTED  # not in this tracker's adapters
    assert db.get(Streamer, in_window.id).platform_channel_id == "tw-1"  # type: ignore[union-attr]


async def test_not_configured(db: Session, fake: FakeAdapter, tracker: Tracker) -> None:
    fake.configured = False
    s = _streamer(db)
    await tracker.run_cycle(now=MON_2030)
    assert _status(db, s.id).state is TrackingState.NOT_CONFIGURED
    assert fake.calls == []


async def test_transitions_create_single_events(db: Session, tracker: Tracker, fake: FakeAdapter) -> None:
    s = _streamer(db)
    fake.live = {s.id}
    r1 = await tracker.run_cycle(now=MON_2030)
    assert _status(db, s.id).state is TrackingState.LIVE
    assert [e["type"] for e in r1.events] == ["stream.went_live"]

    # An error in between must not duplicate the went_live event
    fake.fail = PlatformError("geçici hata")
    await tracker.run_cycle(now=MON_2030 + timedelta(minutes=3))
    assert _status(db, s.id).state is TrackingState.ERROR
    assert _status(db, s.id).error_message == "geçici hata"
    fake.fail = None
    r3 = await tracker.run_cycle(now=MON_2030 + timedelta(minutes=6))
    assert r3.events == []

    fake.live = set()
    r4 = await tracker.run_cycle(now=MON_2030 + timedelta(minutes=9))
    assert [e["type"] for e in r4.events] == ["stream.went_offline"]
    types = db.scalars(select(StreamEvent.event_type).order_by(StreamEvent.id)).all()
    assert types == [StreamEventType.WENT_LIVE, StreamEventType.WENT_OFFLINE]


async def test_poll_interval_and_force(db: Session, tracker: Tracker, fake: FakeAdapter) -> None:
    s = _streamer(db)
    await tracker.run_cycle(now=MON_2030)
    await tracker.run_cycle(now=MON_2030 + timedelta(seconds=60))  # interval (120s) not elapsed
    assert len(fake.calls) == 1
    await tracker.run_cycle(now=MON_2030 + timedelta(seconds=121))
    assert len(fake.calls) == 2
    # Forced checks ignore interval and schedule
    await tracker.run_cycle(now=MON_2030 + timedelta(seconds=122), force_ids={s.id})
    await tracker.run_cycle(now=MON_2030 + timedelta(days=2), force_ids={s.id})
    assert len(fake.calls) == 4


async def test_unexpected_adapter_bug_is_contained(db: Session, tracker: Tracker, fake: FakeAdapter) -> None:
    s = _streamer(db)

    async def boom(channels):  # type: ignore[no-untyped-def]
        raise RuntimeError("bug")

    fake.check = boom  # type: ignore[method-assign]
    await tracker.run_cycle(now=MON_2030)
    assert _status(db, s.id).state is TrackingState.ERROR


# --- API ----------------------------------------------------------------------
def test_schedule_put_get_and_validation(api: TestClient, db: Session) -> None:
    s = _streamer(db, windows=[])
    url = f"/api/v1/streamers/{s.id}/schedule"
    body = {"windows": [{"day_of_week": 4, "start_time": "22:00", "end_time": "02:00"}, {"day_of_week": 0, "start_time": "20:00", "end_time": "23:00"}]}
    data = api.put(url, json=body).json()
    assert [w["day_of_week"] for w in data["windows"]] == [0, 4]
    assert data["timezone"] == "Europe/Istanbul"
    assert len(api.get(url).json()["windows"]) == 2

    assert api.put(url, json={"windows": [{"day_of_week": 7, "start_time": "20:00", "end_time": "21:00"}]}).status_code == 422
    assert api.put(url, json={"windows": [{"day_of_week": 1, "start_time": "25:00", "end_time": "21:00"}]}).status_code == 422
    dup = {"day_of_week": 1, "start_time": "20:00", "end_time": "21:00"}
    assert api.put(url, json={"windows": [dup, dup]}).status_code == 422
    assert api.put(url, json={"windows": [dup] * 29}).status_code == 422
    assert api.put(url, json={"windows": []}).json()["windows"] == []
    assert api.put("/api/v1/streamers/999/schedule", json={"windows": []}).status_code == 404


def test_overview_and_check_now(api: TestClient, db: Session, fake: FakeAdapter) -> None:
    s = _streamer(db, windows=[(d, "00:00", "00:00") for d in range(7)])  # 7/24
    overview = api.get("/api/v1/tracking/overview").json()
    item = overview["streamers"][0]
    assert item["status"]["state"] == "pending"
    assert item["in_schedule"] is True and item["next_change_at"] is not None
    assert {p["platform"]: p["configured"] for p in overview["platforms"]} == {"twitch": True}

    fake.live = {s.id}
    checked = api.post(f"/api/v1/tracking/streamers/{s.id}/check").json()
    assert checked["status"]["state"] == "live"
    assert api.get("/api/v1/tracking/overview").json()["live_count"] == 1
    events = api.get("/api/v1/tracking/events").json()
    assert events[0]["event_type"] == "went_live" and events[0]["streamer_name"] == "A"
    assert api.get("/api/v1/dashboard/summary").json()["stats"]["active_streams"] == 1
    assert api.post("/api/v1/tracking/streamers/999/check").status_code == 404


def test_url_change_resets_platform_state(api: TestClient, db: Session, fake: FakeAdapter) -> None:
    s = _streamer(db)
    api.post(f"/api/v1/tracking/streamers/{s.id}/check")
    db.expire_all()
    assert db.get(Streamer, s.id).platform_channel_id == "tw-1"  # type: ignore[union-attr]
    api.patch(f"/api/v1/streamers/{s.id}", json={"channel_url": "https://twitch.tv/renamed"})
    db.expire_all()
    assert db.get(Streamer, s.id).platform_channel_id is None  # type: ignore[union-attr]
    assert db.get(StreamStatus, s.id) is None
