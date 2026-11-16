"""Live capture: one yt-dlp (+FFmpeg) subprocess per recording session.

Safety rails, all enforced here rather than in the UI:
* ``ensure_recording_permitted`` + the per-streamer ``live_capture_enabled`` opt-in.
* Max concurrent recordings, max duration, minimum free disk space.
* A stream the operator stopped (``stop_reason == "manual"``) is never auto-restarted,
  and a failing stream is retried at most ``MAX_FAILURES_PER_STREAM`` times.
* On shutdown captures are stopped gracefully; on startup interrupted sessions are
  recovered and the captured part is kept.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
import signal
import sys
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, NotFoundError, RecordingNotPermittedError
from app.database.base import utcnow
from app.database.session import get_session_factory
from app.models import RecordingSession, RecordingSource, RecordingStatus, StreamStatus, Streamer, TrackingState
from app.services.recorder import storage
from app.services.streamer.base import ensure_recording_permitted
from app.services.video.base import MediaError, ffmpeg_path, is_mpegts, probe, remux_to_mp4
from app.websocket.manager import manager as ws

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = (RecordingStatus.RECORDING, RecordingStatus.PROCESSING)
MAX_FAILURES_PER_STREAM = 3
RETRY_COOLDOWN = timedelta(minutes=2)
STOP_GRACE_SECONDS = 30
_NOT_MEDIA = {".log", ".part", ".ytdl", ".tmp"}

STOP_MANUAL = "manual"
STOP_STREAM_ENDED = "stream_ended"
STOP_MAX_DURATION = "max_duration"
STOP_SHUTDOWN = "shutdown"
STOP_ERROR = "error"

CommandFactory = Callable[[str, Path], list[str]]


class RecordingUnavailableError(AppError):
    status_code = 409
    code = "recording_unavailable"


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _captured_files(base: Path) -> list[Path]:
    """Media files written for ``base`` (any extension), largest first."""
    if not base.parent.exists():
        return []
    files = [p for p in base.parent.glob(f"{base.name}.*") if p.suffix not in _NOT_MEDIA and p.stat().st_size > 0]
    return sorted(files, key=lambda p: p.stat().st_size, reverse=True)


def _log_tail(path: Path, lines: int = 3) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    except OSError:
        return ""
    errors = [line for line in text if "ERROR" in line] or text
    return " ".join(errors[-lines:])[:400]


def _to_mp4_or_keep(source: Path, final: Path, ffmpeg: str) -> tuple[Path, str | None]:
    """Remux to MP4; if the codecs cannot live in MP4, keep the captured file as-is.

    Returns the file to register and an optional note. Raises ``MediaError`` only
    when the captured file itself is unreadable.
    """
    if source == final:
        if not is_mpegts(source):
            return final, None  # already a real MP4
        # An MPEG-TS stream with an .mp4 name: give it its real extension, then remux.
        source = source.rename(source.with_suffix(".ts"))
    try:
        remux_to_mp4(source, final, ffmpeg)
    except MediaError:
        probe(source, ffmpeg)  # still a readable video? then keep it
        return source, f"MP4'e dönüştürülemedi; kayıt orijinal {source.suffix} biçiminde korundu."
    source.unlink(missing_ok=True)
    return final, None


def _emit(event: dict[str, Any]) -> None:
    """Fire-and-forget WebSocket broadcast from sync code running inside the event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(ws.broadcast(event))


class RecordingManager:
    def __init__(
        self,
        settings: Settings,
        session_factory: Callable[[], Session] | None = None,
        command_factory: CommandFactory | None = None,
    ) -> None:
        self.settings = settings
        self._session_factory = session_factory or get_session_factory()
        self._command_factory = command_factory or self.ytdlp_command
        self._procs: dict[int, asyncio.subprocess.Process] = {}
        self._tasks: dict[int, asyncio.Task] = {}
        self._stop_reasons: dict[int, str] = {}
        self._lock = asyncio.Lock()

    # --- tools --------------------------------------------------------------
    @property
    def ffmpeg(self) -> str | None:
        return ffmpeg_path(self.settings.ffmpeg_binary)

    def ytdlp_command(self, url: str, output_base: Path) -> list[str]:
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--no-progress", "--no-part", "--no-playlist", "--hls-use-mpegts",
            "--socket-timeout", "30",
            "-S", self.settings.recording_format_sort, "-f", "bv*+ba/b",
            # --hls-use-mpegts writes MPEG-TS (stays readable if the process dies) but yt-dlp
            # still names it "<base>.mp4"; _to_mp4_or_keep sniffs the content and remuxes it.
            "-o", f"{output_base}.%(ext)s",
            # Keep the log small and free of signed media URLs / client IP (FFmpeg info output).
            "--downloader-args", "ffmpeg_i:-nostats -loglevel warning",
        ]  # fmt: skip
        if self.ffmpeg:
            cmd += ["--ffmpeg-location", self.ffmpeg]
        if shutil.which("node"):
            cmd += ["--js-runtimes", "node"]  # YouTube player challenges need a JS runtime
        return [*cmd, url]

    def active_ids(self) -> set[int]:
        return set(self._procs)

    # --- start / stop -------------------------------------------------------
    async def start_live(self, streamer_id: int) -> int:
        """Start capturing a streamer that is live right now. Returns the session id."""
        async with self._lock:
            with self._session_factory() as db:
                streamer = db.get(Streamer, streamer_id, options=[selectinload(Streamer.stream_status)])
                if streamer is None:
                    raise NotFoundError("Yayıncı bulunamadı.", details={"id": streamer_id})
                ensure_recording_permitted(streamer)
                if not streamer.live_capture_enabled:
                    raise RecordingNotPermittedError(
                        f"'{streamer.name}' için canlı kayıt kapalı. Yayıncı ayarlarından açabilirsiniz."
                    )
                status = streamer.stream_status
                if status is None or status.state is not TrackingState.LIVE or not status.stream_url:
                    raise RecordingUnavailableError("Yayıncı şu an canlı görünmüyor; önce canlı durumunu kontrol edin.")
                if active_session(db, streamer.id) is not None:
                    raise RecordingUnavailableError("Bu yayıncı için zaten devam eden bir kayıt var.")
                if len(self._procs) >= self.settings.recording_max_concurrent:
                    raise RecordingUnavailableError(
                        f"Aynı anda en fazla {self.settings.recording_max_concurrent} kayıt yapılabilir."
                    )
                free = storage.free_gb(self.settings)
                if free < self.settings.recording_min_free_gb:
                    raise RecordingUnavailableError(
                        f"Diskte yeterli boş alan yok ({free:.1f} GB; en az {self.settings.recording_min_free_gb:g} GB gerekli)."
                    )
                if not self.ffmpeg:
                    raise RecordingUnavailableError("FFmpeg bulunamadı; kayıt başlatılamıyor.")

                now = utcnow()
                session = RecordingSession(
                    streamer_id=streamer.id,
                    source=RecordingSource.LIVE_CAPTURE,
                    title=status.title,
                    source_url=status.stream_url,
                    platform_stream_id=status.platform_stream_id or status.stream_url,
                    started_at=now,
                    status=RecordingStatus.RECORDING,
                )
                db.add(session)
                db.flush()
                base = storage.new_base_path(self.settings, streamer.id, streamer.name, session.id, now.astimezone())
                session.file_path = storage.to_relative(self.settings, base.with_suffix(".mp4"))
                db.commit()
                session_id, name, url = session.id, streamer.name, status.stream_url

            log_path = base.with_suffix(".log")
            try:
                with log_path.open("wb") as log:
                    proc = await asyncio.create_subprocess_exec(
                        *self._command_factory(url, base),
                        stdin=asyncio.subprocess.DEVNULL,
                        stdout=log,
                        stderr=asyncio.subprocess.STDOUT,
                    )
            except OSError as exc:
                self._finish(session_id, RecordingStatus.FAILED, error=f"Kayıt aracı başlatılamadı: {exc}", reason=STOP_ERROR)
                raise RecordingUnavailableError("Kayıt aracı başlatılamadı.") from exc

            self._procs[session_id] = proc
            deadline = now + timedelta(hours=self.settings.recording_max_hours)
            self._tasks[session_id] = asyncio.create_task(self._watch(session_id, proc, base, log_path, deadline))

        logger.info("Recording %s started for streamer id=%s (pid=%s)", session_id, streamer_id, proc.pid)
        await ws.broadcast({"type": "recording.started", "recording_id": session_id, "streamer_id": streamer_id, "name": name})
        return session_id

    async def stop(self, session_id: int, reason: str = STOP_MANUAL) -> None:
        """Ask a running capture to finish; its watcher finalizes the file."""
        proc = self._procs.get(session_id)
        if proc is None:
            with self._session_factory() as db:
                if db.get(RecordingSession, session_id) is None:
                    raise NotFoundError("Kayıt bulunamadı.", details={"id": session_id})
            raise RecordingUnavailableError("Bu kayıt şu an devam etmiyor.")
        self._stop_reasons.setdefault(session_id, reason)
        await self._terminate(proc)

    @staticmethod
    async def _terminate(proc: asyncio.subprocess.Process) -> None:
        if proc.returncode is not None:
            return
        with contextlib.suppress(ProcessLookupError):
            proc.send_signal(signal.SIGINT)  # yt-dlp / ffmpeg finalize the output on SIGINT
        try:
            await asyncio.wait_for(proc.wait(), STOP_GRACE_SECONDS)
            return
        except asyncio.TimeoutError:
            pass
        with contextlib.suppress(ProcessLookupError):
            proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), 10)
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()

    # --- lifecycle ----------------------------------------------------------
    async def _watch(self, session_id: int, proc: asyncio.subprocess.Process, base: Path, log_path: Path, deadline: datetime) -> None:
        try:
            remaining = max((deadline - utcnow()).total_seconds(), 1)
            try:
                await asyncio.wait_for(proc.wait(), remaining)
            except asyncio.TimeoutError:
                self._stop_reasons.setdefault(session_id, STOP_MAX_DURATION)
                logger.info("Recording %s reached the %gh limit; stopping.", session_id, self.settings.recording_max_hours)
                await self._terminate(proc)
            await self._finalize(session_id, proc.returncode, base, log_path)
        except Exception:  # noqa: BLE001
            logger.exception("Recording %s watcher failed", session_id)
            self._finish(session_id, RecordingStatus.FAILED, error="Kayıt sonlandırılırken beklenmeyen bir hata oluştu.", reason=STOP_ERROR)
        finally:
            self._procs.pop(session_id, None)
            self._tasks.pop(session_id, None)
            self._stop_reasons.pop(session_id, None)

    async def _finalize(self, session_id: int, returncode: int | None, base: Path, log_path: Path) -> None:
        requested = self._stop_reasons.get(session_id)
        captured = _captured_files(base)
        if not captured:
            detail = _log_tail(log_path) or f"çıkış kodu {returncode}"
            self._finish(session_id, RecordingStatus.FAILED, error=f"Hiç görüntü kaydedilemedi: {detail}", reason=requested or STOP_ERROR)
            return

        self._set_status(session_id, RecordingStatus.PROCESSING)
        _emit({"type": "recording.processing", "recording_id": session_id})
        ffmpeg = self.ffmpeg or "ffmpeg"
        try:
            final, note = await asyncio.to_thread(_to_mp4_or_keep, captured[0], base.with_suffix(".mp4"), ffmpeg)
            for leftover in captured[1:]:
                leftover.unlink(missing_ok=True)
            info = await asyncio.to_thread(probe, final, ffmpeg)
        except MediaError as exc:
            self._finish(session_id, RecordingStatus.FAILED, error=str(exc), file=captured[0], reason=STOP_ERROR)
            return

        if note is None and requested == STOP_MAX_DURATION:
            note = f"Azami kayıt süresine ({self.settings.recording_max_hours:g} saat) ulaşıldığı için durduruldu."
        elif note is None and requested == STOP_SHUTDOWN:
            note = "Backend kapatıldığı için kayıt durduruldu; kaydedilen kısım korundu."
        elif note is None and requested is None and returncode not in (0, None):
            note = f"Kayıt aracı beklenmedik şekilde sonlandı (kod {returncode}); kaydedilen kısım korundu."
        self._finish(
            session_id,
            RecordingStatus.COMPLETED,
            error=note,
            file=final,
            duration=info.duration_seconds,
            reason=requested or STOP_STREAM_ENDED,
        )
        if note is None:
            log_path.unlink(missing_ok=True)  # keep the log only when something went wrong

    def _set_status(self, session_id: int, status: RecordingStatus) -> None:
        with self._session_factory() as db:
            session = db.get(RecordingSession, session_id)
            if session:
                session.status = status
                db.commit()

    def _finish(
        self,
        session_id: int,
        status: RecordingStatus,
        *,
        reason: str,
        error: str | None = None,
        file: Path | None = None,
        duration: float | None = None,
    ) -> None:
        with self._session_factory() as db:
            session = db.get(RecordingSession, session_id)
            if session is None:
                return
            session.status = status
            session.stop_reason = reason
            session.ended_at = session.ended_at or utcnow()
            session.error_message = error
            if file is not None and file.exists():
                session.file_path = storage.to_relative(self.settings, file)
                session.file_size_bytes = file.stat().st_size
            if duration is not None:
                session.duration_seconds = duration
            streamer_id = session.streamer_id
            db.commit()
        logger.info("Recording %s finished: %s (%s)%s", session_id, status.value, reason, f" - {error}" if error else "")
        _emit({"type": "recording.finished", "recording_id": session_id, "streamer_id": streamer_id, "status": status.value})

    # --- automation ---------------------------------------------------------
    async def sync_with_tracking(self, now: datetime | None = None) -> list[int]:
        """Start captures for opted-in live streamers; stop captures whose stream went offline."""
        now = now or utcnow()
        to_start: list[int] = []
        to_stop: list[int] = []
        with self._session_factory() as db:
            rows = db.execute(
                select(Streamer, StreamStatus)
                .join(StreamStatus, StreamStatus.streamer_id == Streamer.id)
                .where(Streamer.live_capture_enabled.is_(True))
            ).all()
            for streamer, status in rows:
                active = active_session(db, streamer.id)
                if active is not None:
                    if status.state is TrackingState.OFFLINE and active.id in self._procs:
                        to_stop.append(active.id)  # stream ended but the capture process is still waiting
                    continue
                if status.state is not TrackingState.LIVE or not streamer.is_active or not streamer.recording_permission_confirmed:
                    continue
                stream_key = status.platform_stream_id or status.stream_url
                previous = db.scalars(
                    select(RecordingSession).where(
                        RecordingSession.streamer_id == streamer.id, RecordingSession.platform_stream_id == stream_key
                    )
                ).all()
                if any(p.stop_reason == STOP_MANUAL for p in previous):
                    continue  # the operator stopped this stream on purpose
                if sum(p.status is RecordingStatus.FAILED for p in previous) >= MAX_FAILURES_PER_STREAM:
                    continue
                last_end = max((_as_utc(p.ended_at) for p in previous if p.ended_at), default=None)
                if last_end is not None and now - last_end < RETRY_COOLDOWN:
                    continue
                to_start.append(streamer.id)

        for session_id in to_stop:
            logger.info("Stream offline; stopping recording %s", session_id)
            with contextlib.suppress(AppError):
                await self.stop(session_id, STOP_STREAM_ENDED)
        started: list[int] = []
        for streamer_id in to_start:
            try:
                started.append(await self.start_live(streamer_id))
            except AppError as exc:
                logger.warning("Auto-recording not started for streamer id=%s: %s", streamer_id, exc.message)
        return started

    def recover_on_startup(self) -> int:
        """Sessions left RECORDING/PROCESSING by a crash or restart: keep what was captured."""
        recovered = 0
        ffmpeg = self.ffmpeg or "ffmpeg"
        with self._session_factory() as db:
            stale = db.scalars(select(RecordingSession).where(RecordingSession.status.in_(ACTIVE_STATUSES))).all()
            for session in stale:
                recovered += 1
                session.ended_at = session.ended_at or utcnow()
                session.stop_reason = STOP_SHUTDOWN
                final = storage.to_absolute(self.settings, session.file_path) if session.file_path else None
                parts = _captured_files(final.with_suffix("")) if final else []
                if final is None or not parts:
                    session.status = RecordingStatus.FAILED
                    session.error_message = "Backend yeniden başladığı için kayıt yarıda kaldı; dosya oluşmamıştı."
                    continue
                try:
                    kept, note = _to_mp4_or_keep(parts[0], final, ffmpeg)
                    info = probe(kept, ffmpeg)
                    session.status = RecordingStatus.COMPLETED
                    session.file_path = storage.to_relative(self.settings, kept)
                    session.file_size_bytes = kept.stat().st_size
                    session.duration_seconds = info.duration_seconds
                    session.error_message = " ".join(
                        filter(None, ["Backend yeniden başladığı için kayıt yarıda kesildi; kaydedilen kısım korundu.", note])
                    )
                except MediaError as exc:
                    session.status = RecordingStatus.FAILED
                    session.error_message = f"Yarıda kalan kayıt kurtarılamadı: {exc}"
            db.commit()
        if recovered:
            logger.warning("Recovered %d interrupted recording session(s).", recovered)
        return recovered

    async def shutdown(self) -> None:
        """Stop all captures gracefully (app shutdown)."""
        running = [(i, p) for i, p in self._procs.items()]
        for session_id, _ in running:
            self._stop_reasons.setdefault(session_id, STOP_SHUTDOWN)
        await asyncio.gather(*(self._terminate(p) for _, p in running), return_exceptions=True)
        await asyncio.gather(*list(self._tasks.values()), return_exceptions=True)


def active_session(db: Session, streamer_id: int) -> RecordingSession | None:
    return db.scalar(
        select(RecordingSession)
        .where(RecordingSession.streamer_id == streamer_id, RecordingSession.status.in_(ACTIVE_STATUSES))
        .limit(1)
    )


@lru_cache
def get_recording_manager() -> RecordingManager:
    return RecordingManager(get_settings())
