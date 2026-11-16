"""Read side of tracking (overview, events) + weekly schedule editing."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import DomainValidationError, NotFoundError
from app.database.base import utcnow
from app.models import RecordingSession, RecordingStatus, StreamEvent, Streamer, TrackingState, TrackingWindow
from app.scheduler.scheduler import tracking_job_next_run
from app.schemas.tracking import (
    PlatformInfo,
    ScheduleRead,
    ScheduleUpdate,
    StreamEventRead,
    StreamStatusRead,
    TrackedStreamer,
    TrackingOverview,
    TrackingWindowRead,
)
from app.services.streamer.schedule import active_window_end, next_window_start
from app.services.streamer.tracking_service import Tracker, windows_of


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def _get_streamer(db: Session, streamer_id: int) -> Streamer:
    streamer = db.get(Streamer, streamer_id, options=[selectinload(Streamer.tracking_windows)])
    if streamer is None:
        raise NotFoundError("Yayıncı bulunamadı.", details={"id": streamer_id})
    return streamer


# --- schedule ----------------------------------------------------------------
def get_schedule(db: Session, streamer_id: int, tz_name: str) -> ScheduleRead:
    streamer = _get_streamer(db, streamer_id)
    return ScheduleRead(
        streamer_id=streamer.id,
        timezone=tz_name,
        windows=[TrackingWindowRead.model_validate(w) for w in streamer.tracking_windows],
    )


def replace_schedule(db: Session, streamer_id: int, payload: ScheduleUpdate, tz_name: str) -> ScheduleRead:
    streamer = _get_streamer(db, streamer_id)
    keys = [(w.day_of_week, w.start_time, w.end_time) for w in payload.windows]
    if len(keys) != len(set(keys)):
        raise DomainValidationError("windows", "Aynı gün ve saat aralığı birden fazla kez eklenmiş.")
    db.execute(delete(TrackingWindow).where(TrackingWindow.streamer_id == streamer.id))
    for day, start, end in sorted(keys):
        db.add(TrackingWindow(streamer_id=streamer.id, day_of_week=day, start_time=start, end_time=end))
    db.commit()
    db.expire(streamer, ["tracking_windows"])
    return get_schedule(db, streamer_id, tz_name)


# --- overview ----------------------------------------------------------------
def build_overview(db: Session, tracker: Tracker) -> TrackingOverview:
    settings = tracker.settings
    tz = ZoneInfo(settings.scheduler_timezone)
    local_now = utcnow().astimezone(tz)
    streamers = db.scalars(
        select(Streamer)
        .options(selectinload(Streamer.tracking_windows), selectinload(Streamer.stream_status))
        .order_by(Streamer.is_active.desc(), Streamer.name)
    ).all()

    active_recordings = dict(
        db.execute(
            select(RecordingSession.streamer_id, RecordingSession.id).where(
                RecordingSession.status.in_((RecordingStatus.RECORDING, RecordingStatus.PROCESSING))
            )
        ).all()
    )
    items: list[TrackedStreamer] = []
    for s in streamers:
        windows = windows_of(s)
        current_end = active_window_end(windows, local_now)
        next_change = current_end or next_window_start(windows, local_now)
        status = (
            StreamStatusRead.model_validate(s.stream_status)
            if s.stream_status
            else StreamStatusRead(state=TrackingState.PENDING)
        )
        for attr in ("live_started_at", "checked_at", "state_changed_at"):
            setattr(status, attr, _utc(getattr(status, attr)))
        items.append(
            TrackedStreamer(
                id=s.id,
                name=s.name,
                platform=s.platform,
                channel_url=s.channel_url,
                is_active=s.is_active,
                recording_permission_confirmed=s.recording_permission_confirmed,
                live_capture_enabled=s.live_capture_enabled,
                active_recording_id=active_recordings.get(s.id),
                windows=[TrackingWindowRead.model_validate(w) for w in s.tracking_windows],
                status=status,
                in_schedule=current_end is not None,
                next_change_at=_utc(next_change),
            )
        )

    platforms = [
        PlatformInfo(
            platform=platform,
            configured=adapter.is_configured(),
            required_settings=list(adapter.required_settings),
            poll_interval_seconds=adapter.poll_interval_seconds,
        )
        for platform, adapter in tracker.adapters.items()
    ]
    return TrackingOverview(
        timezone=settings.scheduler_timezone,
        tracking_enabled=settings.tracking_enabled and settings.scheduler_enabled,
        tick_seconds=settings.tracking_tick_seconds,
        next_cycle_at=_utc(tracking_job_next_run()),
        live_count=sum(1 for i in items if i.status.state is TrackingState.LIVE),
        platforms=platforms,
        streamers=items,
    )


def list_events(db: Session, limit: int) -> list[StreamEventRead]:
    rows = db.execute(
        select(StreamEvent, Streamer.name, Streamer.platform)
        .join(Streamer)
        .order_by(StreamEvent.occurred_at.desc(), StreamEvent.id.desc())
        .limit(limit)
    ).all()
    return [
        StreamEventRead(
            id=e.id,
            streamer_id=e.streamer_id,
            streamer_name=name,
            platform=platform,
            event_type=e.event_type,
            title=e.title,
            occurred_at=_utc(e.occurred_at),  # type: ignore[arg-type]
        )
        for e, name, platform in rows
    ]
