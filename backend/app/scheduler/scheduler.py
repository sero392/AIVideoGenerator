"""APScheduler wiring. Phase 1 only runs a heartbeat; stream polling jobs come in phase 2."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import Settings
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

HEARTBEAT_SECONDS = 30


async def _heartbeat() -> None:
    await manager.broadcast({"type": "heartbeat", "timestamp": datetime.now(timezone.utc).isoformat()})


def start_scheduler(settings: Settings) -> AsyncIOScheduler | None:
    global _scheduler
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled by configuration.")
        return None
    _scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
    _scheduler.add_job(_heartbeat, "interval", seconds=HEARTBEAT_SECONDS, id="system.heartbeat", replace_existing=True)
    _scheduler.start()
    logger.info("Scheduler started (%s).", settings.scheduler_timezone)
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def scheduler_is_running() -> bool:
    return bool(_scheduler and _scheduler.running)
