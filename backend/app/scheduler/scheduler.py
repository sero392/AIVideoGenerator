"""APScheduler wiring: heartbeat + live tracking tick."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import Settings
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

HEARTBEAT_SECONDS = 30
TRACKING_JOB_ID = "tracking.poll"


async def _heartbeat() -> None:
    await manager.broadcast({"type": "heartbeat", "timestamp": datetime.now(timezone.utc).isoformat()})


async def _tracking_tick() -> None:
    # Imported lazily: the tracker builds DB sessions and HTTP adapters.
    from app.services.recorder.manager import get_recording_manager
    from app.services.streamer.tracking_service import get_tracker

    try:
        await get_tracker().run_cycle()
    except Exception:  # noqa: BLE001  (a failing tick must not kill the scheduler)
        logger.exception("Tracking cycle failed")
    try:
        await get_recording_manager().sync_with_tracking()
    except Exception:  # noqa: BLE001
        logger.exception("Recording sync failed")


def start_scheduler(settings: Settings) -> AsyncIOScheduler | None:
    global _scheduler
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled by configuration.")
        return None
    _scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
    _scheduler.add_job(_heartbeat, "interval", seconds=HEARTBEAT_SECONDS, id="system.heartbeat", replace_existing=True)
    if settings.tracking_enabled:
        _scheduler.add_job(
            _tracking_tick,
            "interval",
            seconds=settings.tracking_tick_seconds,
            id=TRACKING_JOB_ID,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            next_run_time=datetime.now(timezone.utc) + timedelta(seconds=5),
        )
    _scheduler.start()
    logger.info(
        "Scheduler started (%s, tracking %s).",
        settings.scheduler_timezone,
        f"every {settings.tracking_tick_seconds}s" if settings.tracking_enabled else "disabled",
    )
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def scheduler_is_running() -> bool:
    return bool(_scheduler and _scheduler.running)


def tracking_job_next_run() -> datetime | None:
    job = _scheduler.get_job(TRACKING_JOB_ID) if _scheduler else None
    return job.next_run_time if job else None
