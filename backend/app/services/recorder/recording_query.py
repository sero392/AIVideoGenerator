"""Read side + deletion for recordings."""

from __future__ import annotations

import importlib.metadata
import shutil
from datetime import timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import PROJECT_ROOT, Settings
from app.core.exceptions import ConflictError, NotFoundError, UnsafePathError
from app.models import Clip, RecordingSession, RecordingSource, RecordingStatus, Streamer
from app.schemas.recording import RecordingList, RecordingRead, RecordingSystemInfo
from app.services.recorder import storage
from app.services.recorder.manager import ACTIVE_STATUSES, RecordingManager, _captured_files
from app.services.video.base import ffmpeg_path


def _utc(value):  # type: ignore[no-untyped-def]
    if value is None:
        return None
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def to_read(settings: Settings, session: RecordingSession, streamer: Streamer) -> RecordingRead:
    path = None
    if session.file_path:
        try:
            path = storage.to_absolute(settings, session.file_path)
        except UnsafePathError:
            path = None
    size = session.file_size_bytes
    available = bool(path and path.is_file() and session.status is RecordingStatus.COMPLETED)
    if session.status in ACTIVE_STATUSES and path is not None:
        size = sum(p.stat().st_size for p in _captured_files(path.with_suffix(""))) or None
    return RecordingRead(
        id=session.id,
        streamer_id=session.streamer_id,
        streamer_name=streamer.name,
        platform=streamer.platform,
        source=session.source,
        title=session.title,
        source_url=session.source_url,
        status=session.status,
        stop_reason=session.stop_reason,
        started_at=_utc(session.started_at),
        ended_at=_utc(session.ended_at),
        duration_seconds=session.duration_seconds,
        file_size_bytes=size,
        file_available=available,
        error_message=session.error_message,
        created_at=_utc(session.created_at),
    )


def list_recordings(
    db: Session,
    settings: Settings,
    *,
    streamer_id: int | None,
    status: RecordingStatus | None,
    source: RecordingSource | None,
    limit: int,
    offset: int,
) -> RecordingList:
    filters = []
    if streamer_id is not None:
        filters.append(RecordingSession.streamer_id == streamer_id)
    if status is not None:
        filters.append(RecordingSession.status == status)
    if source is not None:
        filters.append(RecordingSession.source == source)
    total = int(db.scalar(select(func.count(RecordingSession.id)).where(*filters)) or 0)
    rows = db.execute(
        select(RecordingSession, Streamer)
        .join(Streamer)
        .where(*filters)
        .order_by(RecordingSession.created_at.desc(), RecordingSession.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return RecordingList(items=[to_read(settings, r, s) for r, s in rows], total=total, limit=limit, offset=offset)


def get_recording(db: Session, settings: Settings, recording_id: int) -> RecordingRead:
    row = db.execute(select(RecordingSession, Streamer).join(Streamer).where(RecordingSession.id == recording_id)).first()
    if row is None:
        raise NotFoundError("Kayıt bulunamadı.", details={"id": recording_id})
    return to_read(settings, *row)


def file_for_download(db: Session, settings: Settings, recording_id: int):  # type: ignore[no-untyped-def]
    session = db.get(RecordingSession, recording_id)
    if session is None or not session.file_path or session.status is not RecordingStatus.COMPLETED:
        raise NotFoundError("Kayıt dosyası hazır değil.", details={"id": recording_id})
    path = storage.to_absolute(settings, session.file_path)
    if not path.is_file():
        raise NotFoundError("Kayıt dosyası diskte bulunamadı.", details={"id": recording_id})
    return path


def delete_recording(db: Session, settings: Settings, recording_id: int) -> None:
    session = db.get(RecordingSession, recording_id)
    if session is None:
        raise NotFoundError("Kayıt bulunamadı.", details={"id": recording_id})
    if session.status in ACTIVE_STATUSES:
        raise ConflictError("Devam eden bir kayıt silinemez; önce kaydı durdurun.")
    clips = db.scalar(select(func.count(Clip.id)).where(Clip.recording_id == session.id)) or 0
    if clips:
        raise ConflictError(f"Bu kayıttan üretilmiş {clips} kesit var; önce kesitleri silin.")
    if session.file_path:
        base = storage.to_absolute(settings, session.file_path).with_suffix("")
        for path in base.parent.glob(f"{base.name}.*"):
            path.unlink(missing_ok=True)
    db.delete(session)
    db.commit()


def system_info(db: Session, settings: Settings, manager: RecordingManager) -> RecordingSystemInfo:
    ffmpeg = ffmpeg_path(settings.ffmpeg_binary)
    try:
        ytdlp = importlib.metadata.version("yt-dlp")
    except importlib.metadata.PackageNotFoundError:
        ytdlp = None
    inbox = storage.inbox_dir(settings)
    try:
        inbox_display = inbox.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        inbox_display = str(inbox)
    return RecordingSystemInfo(
        ffmpeg_available=ffmpeg is not None,
        ffmpeg_source=None if ffmpeg is None else ("system" if shutil.which(settings.ffmpeg_binary) else "bundled"),
        ytdlp_version=ytdlp,
        js_runtime_available=shutil.which("node") is not None,
        free_gb=round(storage.free_gb(settings), 1),
        min_free_gb=settings.recording_min_free_gb,
        max_concurrent=settings.recording_max_concurrent,
        active_count=len(manager.active_ids()),
        max_hours=settings.recording_max_hours,
        max_upload_gb=settings.recording_max_upload_gb,
        inbox_path=inbox_display,
        allowed_extensions=sorted(storage.VIDEO_EXTENSIONS),
    )
