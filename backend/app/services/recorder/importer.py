"""Import recordings the streamer provided (browser upload or the inbox folder).

This is the default, terms-friendly path: the file comes from the rights holder
(e.g. downloaded from their own YouTube Studio) instead of being captured.
Every file is probed with FFmpeg, then stored as web-playable MP4 when a lossless
remux is possible (otherwise the original container is kept).
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import DomainValidationError, NotFoundError, RecordingNotPermittedError
from app.database.base import utcnow
from app.models import RecordingSession, RecordingSource, RecordingStatus, Streamer
from app.services.recorder import storage
from app.services.video.base import MediaError, is_mpegts, probe, remux_to_mp4, require_ffmpeg

logger = logging.getLogger(__name__)


def check_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in storage.VIDEO_EXTENSIONS:
        allowed = ", ".join(sorted(storage.VIDEO_EXTENSIONS))
        raise DomainValidationError("file", f"Desteklenmeyen dosya türü ({ext or 'uzantısız'}). İzin verilenler: {allowed}")
    return ext


def _permitted_streamer(db: Session, streamer_id: int) -> Streamer:
    streamer = db.get(Streamer, streamer_id)
    if streamer is None:
        raise NotFoundError("Yayıncı bulunamadı.", details={"id": streamer_id})
    if not streamer.recording_permission_confirmed:
        raise RecordingNotPermittedError(
            f"'{streamer.name}' için kayıt/yeniden yayın izni onaylanmamış; önce Yayıncı Yönetimi'nden izni onaylayın."
        )
    return streamer


def import_file(
    db: Session,
    settings: Settings,
    *,
    streamer_id: int,
    source: Path,
    original_name: str,
    title: str | None = None,
    move: bool = True,
) -> RecordingSession:
    """Take ownership of ``source`` (moved, or copied when ``move=False``) and register it."""
    streamer = _permitted_streamer(db, streamer_id)
    ext = check_extension(original_name)
    ffmpeg = require_ffmpeg(settings.ffmpeg_binary)

    now = utcnow()
    session = RecordingSession(
        streamer_id=streamer.id,
        source=RecordingSource.IMPORT,
        title=(title or Path(original_name).stem)[:300],
        source_url=Path(original_name).name[:500],
        status=RecordingStatus.PROCESSING,
    )
    db.add(session)
    db.flush()
    base = storage.new_base_path(settings, streamer.id, streamer.name, session.id, now.astimezone())
    db.commit()

    original = base.with_suffix(ext)
    try:
        (shutil.move if move else shutil.copy2)(str(source), str(original))
        info = probe(original, ffmpeg)
        if not info.has_video:
            raise MediaError("Dosyada video akışı bulunamadı.")
        final = original
        if ext == ".mp4" and is_mpegts(original):
            # MPEG-TS content with an .mp4 name (e.g. some capture tools): browsers cannot play it.
            original = original.rename(base.with_suffix(".ts"))
            final = original
        if final.suffix != ".mp4":
            try:
                remux_to_mp4(original, base.with_suffix(".mp4"), ffmpeg)
                original.unlink(missing_ok=True)
                final = base.with_suffix(".mp4")
            except MediaError:
                logger.info("Recording %s kept as %s (codec not MP4-compatible)", session.id, final.suffix)
        session.file_path = storage.to_relative(settings, final)
        session.file_size_bytes = final.stat().st_size
        session.duration_seconds = info.duration_seconds
        session.status = RecordingStatus.COMPLETED
        session.ended_at = utcnow()
    except (MediaError, OSError) as exc:
        original.unlink(missing_ok=True)
        session.status = RecordingStatus.FAILED
        session.error_message = str(exc) if isinstance(exc, MediaError) else "Dosya kaydedilemedi."
        session.ended_at = utcnow()
        db.commit()
        raise DomainValidationError("file", session.error_message) from exc
    db.commit()
    logger.info("Recording %s imported for streamer id=%s (%s)", session.id, streamer.id, final.name)
    return session


@dataclass
class InboxScanResult:
    imported: list[int] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)


def scan_inbox(db: Session, settings: Settings) -> InboxScanResult:
    """Import ``storage/recordings/inbox/<streamer_id>/*``. Failed files stay for inspection."""
    result = InboxScanResult()
    inbox = storage.inbox_dir(settings)
    for folder in sorted(p for p in inbox.iterdir() if p.is_dir()):
        if not folder.name.isdigit():
            result.errors.append({"file": folder.name, "message": "Klasör adı yayıncı numarası olmalı (ör. inbox/2/)."})
            continue
        for file in sorted(p for p in folder.iterdir() if p.is_file() and not p.name.startswith(".")):
            rel = f"{folder.name}/{file.name}"
            try:
                session = import_file(db, settings, streamer_id=int(folder.name), source=file, original_name=file.name)
                result.imported.append(session.id)
            except (DomainValidationError, NotFoundError, RecordingNotPermittedError) as exc:
                db.rollback()
                result.errors.append({"file": rel, "message": exc.message})
    return result
