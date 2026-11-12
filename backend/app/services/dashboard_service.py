"""Aggregates real numbers from the database for the overview page. No mock data."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.init_db import check_db_connection
from app.models import Clip, ClipStatus, RecordingSession, RecordingStatus, Streamer, YoutubeVideo
from app.scheduler.scheduler import scheduler_is_running
from app.schemas.dashboard import (
    ActivityItem,
    ComponentStatus,
    DashboardStats,
    DashboardSummary,
    SystemStatus,
)
from app.services.ai.registry import AIProviderRegistry
from app.services.video.base import ffmpeg_path, opencv_installed

RECENT_ACTIVITY_LIMIT = 8


def _count(db: Session, stmt) -> int:  # type: ignore[no-untyped-def]
    return int(db.scalar(stmt) or 0)


def get_stats(db: Session) -> DashboardStats:
    return DashboardStats(
        tracked_streamers=_count(db, select(func.count(Streamer.id)).where(Streamer.is_active.is_(True))),
        active_streams=_count(
            db, select(func.count(RecordingSession.id)).where(RecordingSession.status == RecordingStatus.RECORDING)
        ),
        total_recordings=_count(db, select(func.count(RecordingSession.id))),
        prepared_clips=_count(
            db, select(func.count(Clip.id)).where(Clip.status.in_([ClipStatus.READY, ClipStatus.APPROVED]))
        ),
    )


def get_recent_activity(db: Session, limit: int = RECENT_ACTIVITY_LIMIT) -> list[ActivityItem]:
    items: list[ActivityItem] = []

    recordings = db.execute(
        select(RecordingSession, Streamer.name)
        .join(Streamer)
        .order_by(RecordingSession.created_at.desc())
        .limit(limit)
    ).all()
    items += [
        ActivityItem(kind="recording", title=f"{name} yayın kaydı", status=r.status.value, timestamp=r.created_at)
        for r, name in recordings
    ]

    clips = db.scalars(select(Clip).order_by(Clip.created_at.desc()).limit(limit)).all()
    items += [ActivityItem(kind="clip", title=c.title, status=c.status.value, timestamp=c.created_at) for c in clips]

    videos = db.scalars(select(YoutubeVideo).order_by(YoutubeVideo.created_at.desc()).limit(limit)).all()
    items += [ActivityItem(kind="youtube", title=v.title, status=v.status.value, timestamp=v.created_at) for v in videos]

    def _key(item: ActivityItem) -> datetime:
        ts = item.timestamp
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)

    return sorted(items, key=_key, reverse=True)[:limit]


async def get_system_status(db: Session, settings: Settings) -> SystemStatus:
    components: list[ComponentStatus] = []

    db_ok = check_db_connection(db.get_bind())  # type: ignore[arg-type]
    components.append(ComponentStatus(name="database", status="ok" if db_ok else "error", detail="SQLite"))

    registry = AIProviderRegistry(settings)
    ollama = await registry.llm("ollama").health_check()
    components.append(ComponentStatus(name="ollama", status=ollama.status, detail=ollama.detail))

    whisper = registry.transcription().health_check()
    components.append(ComponentStatus(name="faster-whisper", status=whisper.status, detail=whisper.detail))

    ff = ffmpeg_path(settings.ffmpeg_binary)
    components.append(
        ComponentStatus(name="ffmpeg", status="ok" if ff else "unavailable", detail=ff or "ffmpeg not found on PATH")
    )
    components.append(
        ComponentStatus(
            name="opencv",
            status="ok" if opencv_installed() else "unavailable",
            detail=None if opencv_installed() else "opencv not installed (requirements-ai.txt)",
        )
    )

    if not settings.scheduler_enabled:
        components.append(ComponentStatus(name="scheduler", status="disabled"))
    else:
        running = scheduler_is_running()
        components.append(ComponentStatus(name="scheduler", status="ok" if running else "error"))

    components.append(
        ComponentStatus(
            name="youtube",
            status="ok" if settings.youtube_oauth_configured else "unavailable",
            detail="OAuth credentials configured" if settings.youtube_oauth_configured else "OAuth credentials not set",
        )
    )

    if any(c.status == "error" for c in components):
        overall = "error" if not db_ok else "degraded"
    elif any(c.status == "unavailable" for c in components):
        overall = "degraded"
    else:
        overall = "ok"
    return SystemStatus(overall=overall, components=components)


async def get_summary(db: Session, settings: Settings) -> DashboardSummary:
    return DashboardSummary(
        stats=get_stats(db),
        recent_activity=get_recent_activity(db),
        system_status=await get_system_status(db, settings),
        generated_at=datetime.now(timezone.utc),
    )
