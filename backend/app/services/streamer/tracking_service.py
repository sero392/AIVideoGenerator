"""Live tracking: decides who is due, calls platform adapters, stores state, emits events.

Flow per cycle (scheduler tick or manual "check now"):
  for each streamer -> inactive? outside its weekly windows? platform unsupported / not
  configured? poll interval not elapsed? -> otherwise batch it per platform -> adapter.check()
  -> update StreamStatus -> log went_live / went_offline transitions -> WebSocket broadcast.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.database.base import utcnow
from app.database.session import get_session_factory
from app.models import StreamEvent, StreamEventType, StreamPlatform, StreamStatus, Streamer, TrackingState
from app.services.streamer.platforms import ChannelRef, LiveStatus, PlatformAdapter, PlatformError, build_adapters
from app.services.streamer.schedule import Window, is_within_schedule
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

# States in which "poll interval not yet elapsed" means: keep the current result.
_CHECKED_STATES = {TrackingState.LIVE, TrackingState.OFFLINE, TrackingState.ERROR}


@dataclass
class CycleResult:
    checked: int = 0
    changed_streamer_ids: set[int] = field(default_factory=set)
    events: list[dict] = field(default_factory=list)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def windows_of(streamer: Streamer) -> list[Window]:
    return [Window(w.day_of_week, w.start_time, w.end_time) for w in streamer.tracking_windows]


def _set_state(status: StreamStatus, state: TrackingState, now: datetime, result: CycleResult, **fields) -> None:  # type: ignore[no-untyped-def]
    changed = status.state != state
    if state is not TrackingState.LIVE:
        fields = {"title": None, "viewer_count": None, "live_started_at": None, "stream_url": None, "platform_stream_id": None} | fields
    if state is not TrackingState.ERROR:
        fields.setdefault("error_message", None)
    for key, value in fields.items():
        if getattr(status, key) != value:
            setattr(status, key, value)
            changed = True
    if status.state != state:
        status.state = state
        status.state_changed_at = now
    if changed:
        result.changed_streamer_ids.add(status.streamer_id)


class Tracker:
    def __init__(
        self,
        settings: Settings,
        session_factory: Callable[[], Session] | None = None,
        adapters: dict[StreamPlatform, PlatformAdapter] | None = None,
    ) -> None:
        self.settings = settings
        self._session_factory = session_factory or get_session_factory()
        self.adapters = adapters if adapters is not None else build_adapters(settings)
        self._lock = asyncio.Lock()

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.settings.scheduler_timezone)

    async def run_cycle(self, *, force_ids: set[int] | None = None, now: datetime | None = None) -> CycleResult:
        """One tracking pass. ``force_ids`` checks only those streamers, ignoring schedule and interval."""
        async with self._lock:  # scheduler tick and manual checks never overlap
            result = await self._run(force_ids, now or utcnow())
        await self._broadcast(result)
        return result

    async def _run(self, force_ids: set[int] | None, now: datetime) -> CycleResult:
        result = CycleResult()
        local_now = now.astimezone(self.timezone)
        with self._session_factory() as db:
            stmt = select(Streamer).options(selectinload(Streamer.tracking_windows), selectinload(Streamer.stream_status))
            if force_ids is not None:
                stmt = stmt.where(Streamer.id.in_(force_ids))
            streamers = db.scalars(stmt).all()

            due: dict[StreamPlatform, list[Streamer]] = defaultdict(list)
            for s in streamers:
                if s.stream_status is None:
                    s.stream_status = StreamStatus(streamer_id=s.id, state=TrackingState.PENDING)
                    db.add(s.stream_status)
                    result.changed_streamer_ids.add(s.id)
                status = s.stream_status
                forced = force_ids is not None

                if not s.is_active and not forced:
                    _set_state(status, TrackingState.INACTIVE, now, result)
                    continue
                if not forced and not is_within_schedule(windows_of(s), local_now):
                    _set_state(status, TrackingState.OUTSIDE_SCHEDULE, now, result)
                    continue
                adapter = self.adapters.get(s.platform)
                if adapter is None:
                    _set_state(status, TrackingState.UNSUPPORTED, now, result)
                    continue
                if not adapter.is_configured():
                    _set_state(status, TrackingState.NOT_CONFIGURED, now, result)
                    continue
                last = _as_utc(status.checked_at)
                if (
                    not forced
                    and status.state in _CHECKED_STATES
                    and last is not None
                    and (now - last).total_seconds() < adapter.poll_interval_seconds
                ):
                    continue
                due[s.platform].append(s)
            db.commit()

            for platform, items in due.items():
                adapter = self.adapters[platform]
                refs = [
                    ChannelRef(
                        s.id,
                        s.channel_url,
                        s.platform_channel_id,
                        known_stream_id=s.stream_status.platform_stream_id if s.stream_status else None,
                    )
                    for s in items
                ]
                try:
                    outcomes = await adapter.check(refs)
                except PlatformError as exc:
                    outcomes = {s.id: exc for s in items}
                except Exception:  # noqa: BLE001  (an adapter bug must not stop the other platforms)
                    logger.exception("Unexpected error in %s adapter", platform.value)
                    outcomes = {s.id: PlatformError("Beklenmeyen bir hata oluştu; ayrıntılar backend logunda.") for s in items}
                for s in items:
                    self._apply(db, s, outcomes.get(s.id) or PlatformError("Platformdan yanıt alınamadı."), now, result)
                    result.checked += 1
            db.commit()
        if result.checked:
            logger.info("Tracking cycle: checked=%d changed=%d events=%d", result.checked, len(result.changed_streamer_ids), len(result.events))
        return result

    def _apply(self, db: Session, s: Streamer, outcome: LiveStatus | PlatformError, now: datetime, result: CycleResult) -> None:
        status = s.stream_status
        assert status is not None
        status.checked_at = now
        if isinstance(outcome, PlatformError):
            _set_state(status, TrackingState.ERROR, now, result, error_message=str(outcome)[:500])
            logger.warning("Live check failed for streamer id=%s: %s", s.id, outcome)
            return

        if outcome.resolved_channel_id and outcome.resolved_channel_id != s.platform_channel_id:
            s.platform_channel_id = outcome.resolved_channel_id

        if outcome.is_live:
            _set_state(
                status,
                TrackingState.LIVE,
                now,
                result,
                title=(outcome.title or "")[:300] or None,
                viewer_count=outcome.viewer_count,
                live_started_at=outcome.started_at,
                stream_url=outcome.stream_url,
                platform_stream_id=outcome.stream_id,
            )
        else:
            _set_state(status, TrackingState.OFFLINE, now, result)

        # Transitions are derived from the event log, so an error or an
        # outside-schedule gap in between never produces duplicate events.
        last_event = db.scalar(
            select(StreamEvent.event_type)
            .where(StreamEvent.streamer_id == s.id)
            .order_by(StreamEvent.occurred_at.desc(), StreamEvent.id.desc())
            .limit(1)
        )
        event_type: StreamEventType | None = None
        if outcome.is_live and last_event in (None, StreamEventType.WENT_OFFLINE):
            event_type = StreamEventType.WENT_LIVE
        elif not outcome.is_live and last_event is StreamEventType.WENT_LIVE:
            event_type = StreamEventType.WENT_OFFLINE
        if event_type is None:
            return
        db.add(StreamEvent(streamer_id=s.id, event_type=event_type, title=status.title, occurred_at=now))
        result.events.append(
            {
                "type": f"stream.{event_type.value}",
                "streamer_id": s.id,
                "name": s.name,
                "platform": s.platform.value,
                "title": status.title,
                "stream_url": status.stream_url,
            }
        )
        logger.info("Streamer id=%s %s", s.id, event_type.value)

    async def _broadcast(self, result: CycleResult) -> None:
        for event in result.events:
            await manager.broadcast(event)
        if result.changed_streamer_ids or result.events:
            await manager.broadcast({"type": "tracking.updated", "streamer_ids": sorted(result.changed_streamer_ids)})


@lru_cache
def get_tracker() -> Tracker:
    """Process-wide tracker (keeps OAuth app tokens cached between cycles)."""
    return Tracker(get_settings())
