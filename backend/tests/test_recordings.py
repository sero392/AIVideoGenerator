"""Recording: live capture lifecycle (real FFmpeg stands in for yt-dlp), import, API."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import RecordingNotPermittedError
from app.database.base import utcnow
from app.database.session import get_session_factory
from app.models import RecordingSession, RecordingSource, RecordingStatus, StreamPlatform, StreamStatus, Streamer, TrackingState
from app.services.recorder import storage
from app.services.recorder.manager import RecordingManager, RecordingUnavailableError
from app.services.video.base import ffmpeg_path

FFMPEG = ffmpeg_path("ffmpeg")
pytestmark = pytest.mark.skipif(FFMPEG is None, reason="FFmpeg not available")


# Same codecs as real YouTube/Twitch/Kick live streams (H.264 + AAC).
X264 = ["-preset", "ultrafast", "-g", "10", "-pix_fmt", "yuv420p"]


def fake_capture(seconds: float, realtime: bool = True, codec: str = "libx264"):  # type: ignore[no-untyped-def]
    """Command factory: FFmpeg writes a synthetic A/V stream to <base>.ts like yt-dlp would."""

    def factory(url: str, base: Path) -> list[str]:
        return [FFMPEG, "-hide_banner", "-loglevel", "error", *(["-re"] if realtime else []),
                "-f", "lavfi", "-i", "testsrc=size=160x120:rate=10", "-f", "lavfi", "-i", "sine=frequency=440",
                "-t", str(seconds), "-c:v", codec, *(X264 if codec == "libx264" else []), "-c:a", "aac", "-f", "mpegts", f"{base}.ts"]  # fmt: skip

    return factory


def failing_capture(url: str, base: Path) -> list[str]:
    return [sys.executable, "-c", "import sys; print('ERROR: [youtube] stream unavailable'); sys.exit(1)"]


@pytest.fixture(scope="session")
def sample_videos(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    out = tmp_path_factory.mktemp("media")
    files = {"mp4": out / "sample.mp4", "mkv": out / "sample.mkv"}
    for path in files.values():
        subprocess.run(
            [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=160x120:rate=10",
             "-f", "lavfi", "-i", "sine", "-t", "2", "-c:v", "libx264", *X264, "-c:a", "aac", str(path)],
            check=True,
        )  # fmt: skip
    (out / "fake.mp4").write_bytes(b"this is not a video")
    files["fake"] = out / "fake.mp4"
    return files


def _live_streamer(db: Session, name: str = "Rec", *, capture: bool = True, permission: bool = True,
                   state: TrackingState = TrackingState.LIVE) -> Streamer:
    s = Streamer(name=name, platform=StreamPlatform.YOUTUBE, channel_url=f"https://youtube.com/@{name.lower()}",
                 recording_permission_confirmed=permission, permission_notes="test" if permission else None,
                 live_capture_enabled=capture)
    s.stream_status = StreamStatus(state=state, title="Canlı test", stream_url="https://www.youtube.com/watch?v=abc",
                                   platform_stream_id=f"vid-{name}")
    db.add(s)
    db.commit()
    return s


def _manager(factory, **settings_overrides) -> RecordingManager:  # type: ignore[no-untyped-def]
    settings = get_settings().model_copy(update=settings_overrides)
    return RecordingManager(settings, get_session_factory(), command_factory=factory)


def _session(db: Session, session_id: int) -> RecordingSession:
    db.expire_all()
    return db.get(RecordingSession, session_id)  # type: ignore[return-value]


async def _wait_done(manager: RecordingManager, timeout: float = 30) -> None:
    for _ in range(int(timeout * 10)):
        if not manager.active_ids() and not manager._tasks:
            return
        await asyncio.sleep(0.1)
    raise AssertionError("recording did not finish")


# --- live capture -------------------------------------------------------------
async def test_capture_until_stream_ends(db: Session) -> None:
    s = _live_streamer(db)
    manager = _manager(fake_capture(1.5, realtime=False))
    session_id = await manager.start_live(s.id)
    await _wait_done(manager)

    rec = _session(db, session_id)
    assert rec.status is RecordingStatus.COMPLETED, rec.error_message
    assert rec.source is RecordingSource.LIVE_CAPTURE and rec.stop_reason == "stream_ended"
    assert rec.title == "Canlı test" and rec.platform_stream_id == "vid-Rec"
    path = storage.to_absolute(manager.settings, rec.file_path)  # type: ignore[arg-type]
    assert path.suffix == ".mp4" and path.stat().st_size == rec.file_size_bytes
    assert rec.duration_seconds == pytest.approx(1.5, abs=0.3)
    assert not path.with_suffix(".ts").exists() and not path.with_suffix(".log").exists()


async def test_unconvertible_capture_is_kept_in_original_container(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """If the captured codecs cannot be stream-copied into MP4, keep the .ts instead of failing."""
    from app.services.recorder import manager as manager_module
    from app.services.video.base import MediaError

    def no_mp4(src: Path, dst: Path, ffmpeg: str) -> None:
        raise MediaError("MP4'e dönüştürülemedi: codec desteklenmiyor")

    monkeypatch.setattr(manager_module, "remux_to_mp4", no_mp4)
    manager = _manager(fake_capture(1, realtime=False))
    session_id = await manager.start_live(_live_streamer(db).id)
    await _wait_done(manager)
    rec = _session(db, session_id)
    assert rec.status is RecordingStatus.COMPLETED and rec.file_path.endswith(".ts")  # type: ignore[union-attr]
    assert "orijinal .ts" in (rec.error_message or "") and rec.duration_seconds


async def test_mpegts_named_mp4_is_remuxed(db: Session) -> None:
    """Regression (real YouTube capture): yt-dlp wrote MPEG-TS into a file called .mp4."""
    def factory(url: str, base: Path) -> list[str]:
        return fake_capture(1.5, realtime=False)(url, base)[:-1] + [f"{base}.mp4"]  # TS muxer, .mp4 name

    manager = _manager(factory)
    session_id = await manager.start_live(_live_streamer(db).id)
    await _wait_done(manager)
    rec = _session(db, session_id)
    path = storage.to_absolute(manager.settings, rec.file_path)  # type: ignore[arg-type]
    assert rec.status is RecordingStatus.COMPLETED and path.suffix == ".mp4"
    assert path.read_bytes()[4:8] == b"ftyp"  # a real MP4 now, playable in browsers
    assert not path.with_suffix(".ts").exists()


def test_ytdlp_command_uses_mpegts_and_quiet_ffmpeg() -> None:
    cmd = _manager(None).ytdlp_command("https://www.youtube.com/watch?v=x", Path("/tmp/base"))
    assert "--hls-use-mpegts" in cmd and cmd[cmd.index("-o") + 1] == "/tmp/base.%(ext)s"
    assert "-loglevel warning" in cmd[cmd.index("--downloader-args") + 1]
    assert cmd[-1] == "https://www.youtube.com/watch?v=x"


async def test_manual_stop_keeps_file_and_blocks_auto_restart(db: Session) -> None:
    s = _live_streamer(db)
    manager = _manager(fake_capture(60))
    session_id = await manager.start_live(s.id)
    await asyncio.sleep(3)
    await manager.stop(session_id)
    await _wait_done(manager)

    rec = _session(db, session_id)
    assert rec.status is RecordingStatus.COMPLETED and rec.stop_reason == "manual"
    assert rec.duration_seconds and rec.duration_seconds > 0.5
    # Stream is still live, but the operator stopped it on purpose
    assert await manager.sync_with_tracking(now=utcnow() + timedelta(hours=1)) == []


async def test_sync_starts_and_stops_with_live_state(db: Session) -> None:
    s = _live_streamer(db)
    _live_streamer(db, "NoOptIn", capture=False)
    manager = _manager(fake_capture(60))
    started = await manager.sync_with_tracking()
    assert len(started) == 1 and manager.active_ids() == set(started)
    assert await manager.sync_with_tracking() == []  # already recording

    status = db.get(StreamStatus, s.id)
    status.state = TrackingState.OFFLINE  # type: ignore[union-attr]
    db.commit()
    await manager.sync_with_tracking()
    await _wait_done(manager)
    assert _session(db, started[0]).stop_reason == "stream_ended"


async def test_failures_are_retried_a_limited_number_of_times(db: Session) -> None:
    s = _live_streamer(db)
    manager = _manager(failing_capture)
    now = utcnow()
    session_ids = []
    for attempt in range(5):
        session_ids += await manager.sync_with_tracking(now=now + timedelta(minutes=5 * (attempt + 1)))
        await _wait_done(manager)
    assert len(session_ids) == 3  # MAX_FAILURES_PER_STREAM
    rec = _session(db, session_ids[0])
    assert rec.status is RecordingStatus.FAILED and "stream unavailable" in (rec.error_message or "")
    assert db.get(Streamer, s.id) is not None


async def test_start_guards(db: Session) -> None:
    manager = _manager(fake_capture(60), recording_max_concurrent=1)
    with pytest.raises(RecordingNotPermittedError):
        await manager.start_live(_live_streamer(db, "Off", capture=False).id)
    with pytest.raises(RecordingNotPermittedError):
        await manager.start_live(_live_streamer(db, "NoPerm", capture=True, permission=False).id)
    with pytest.raises(RecordingUnavailableError, match="canlı görünmüyor"):
        await manager.start_live(_live_streamer(db, "Offline", state=TrackingState.OFFLINE).id)
    with pytest.raises(RecordingUnavailableError, match="boş alan"):
        await _manager(fake_capture(1), recording_min_free_gb=10**9).start_live(_live_streamer(db, "Disk").id)

    first = _live_streamer(db, "First")
    session_id = await manager.start_live(first.id)
    with pytest.raises(RecordingUnavailableError, match="zaten"):
        await manager.start_live(first.id)
    with pytest.raises(RecordingUnavailableError, match="en fazla 1"):
        await manager.start_live(_live_streamer(db, "Second").id)
    await manager.stop(session_id)
    await _wait_done(manager)


async def test_shutdown_stops_gracefully(db: Session) -> None:
    manager = _manager(fake_capture(60))
    session_id = await manager.start_live(_live_streamer(db).id)
    await asyncio.sleep(1.5)
    await manager.shutdown()
    rec = _session(db, session_id)
    assert rec.status is RecordingStatus.COMPLETED and rec.stop_reason == "shutdown"


def test_recover_interrupted_sessions(db: Session, sample_videos: dict[str, Path]) -> None:
    s = _live_streamer(db)
    manager = _manager(fake_capture(1))
    with_file = RecordingSession(streamer_id=s.id, status=RecordingStatus.RECORDING, started_at=utcnow())
    without_file = RecordingSession(streamer_id=s.id, status=RecordingStatus.RECORDING, started_at=utcnow())
    db.add_all([with_file, without_file])
    db.flush()
    for rec in (with_file, without_file):
        base = storage.new_base_path(manager.settings, s.id, s.name, rec.id, utcnow())
        rec.file_path = storage.to_relative(manager.settings, base.with_suffix(".mp4"))
        if rec is with_file:
            subprocess.run([FFMPEG, "-loglevel", "error", "-i", str(sample_videos["mp4"]), "-c", "copy", "-f", "mpegts",
                            f"{base}.ts"], check=True)  # fmt: skip
    db.commit()

    assert manager.recover_on_startup() == 2
    recovered, lost = _session(db, with_file.id), _session(db, without_file.id)
    assert recovered.status is RecordingStatus.COMPLETED, recovered.error_message
    assert "korundu" in (recovered.error_message or "")
    assert recovered.duration_seconds == pytest.approx(2, abs=0.3)
    assert lost.status is RecordingStatus.FAILED


def test_base_path_never_collides_with_existing_files(db: Session) -> None:
    settings = get_settings()
    when = utcnow()
    first = storage.new_base_path(settings, 1, "Same", 7, when)
    first.with_suffix(".ts").write_bytes(b"x")  # e.g. a kept recording whose id was reused
    second = storage.new_base_path(settings, 1, "Same", 7, when)
    assert second != first and second.name == f"{first.name}-2"
    first.with_suffix(".ts").unlink()


# --- import + API ---------------------------------------------------------------
API = "/api/v1/recordings"


def _upload(client: TestClient, streamer_id: int, path: Path, name: str | None = None, title: str | None = None):  # type: ignore[no-untyped-def]
    data = {"streamer_id": str(streamer_id), **({"title": title} if title else {})}
    with path.open("rb") as fh:
        return client.post(f"{API}/import", data=data, files={"file": (name or path.name, fh, "application/octet-stream")})


def test_upload_mp4_and_stream_file(client: TestClient, db: Session, sample_videos: dict[str, Path]) -> None:
    s = _live_streamer(db, capture=False)
    response = _upload(client, s.id, sample_videos["mp4"], title="Turnuva finali")
    assert response.status_code == 201, response.text
    rec = response.json()
    assert rec["status"] == "completed" and rec["source"] == "import" and rec["title"] == "Turnuva finali"
    assert rec["file_available"] and rec["duration_seconds"] == pytest.approx(2, abs=0.3)

    full = client.get(f"{API}/{rec['id']}/file")
    assert full.status_code == 200 and full.headers["content-type"] == "video/mp4"
    partial = client.get(f"{API}/{rec['id']}/file", headers={"Range": "bytes=0-99"})
    assert partial.status_code == 206 and len(partial.content) == 100  # seeking in the browser player

    listed = client.get(API, params={"streamer_id": s.id}).json()
    assert listed["total"] == 1 and listed["items"][0]["streamer_name"] == "Rec"
    assert client.get("/api/v1/dashboard/summary").json()["stats"]["total_recordings"] == 1


def test_upload_mkv_is_remuxed_to_mp4(client: TestClient, db: Session, sample_videos: dict[str, Path]) -> None:
    s = _live_streamer(db, capture=False)
    rec = _upload(client, s.id, sample_videos["mkv"]).json()
    assert rec["status"] == "completed" and rec["title"] == "sample"
    path = storage.to_absolute(get_settings(), _session(db, rec["id"]).file_path)  # type: ignore[arg-type]
    assert path.suffix == ".mp4" and not path.with_suffix(".mkv").exists()


def test_upload_rejections(client: TestClient, db: Session, sample_videos: dict[str, Path]) -> None:
    allowed = _live_streamer(db, capture=False)
    blocked = _live_streamer(db, "NoPerm", capture=False, permission=False)

    assert _upload(client, allowed.id, sample_videos["mp4"], name="evil.exe").status_code == 422
    bad = _upload(client, allowed.id, sample_videos["fake"])
    assert bad.status_code == 422 and "video" in bad.json()["error"]["message"]
    assert client.get(API, params={"status": "failed"}).json()["total"] == 1
    assert _upload(client, blocked.id, sample_videos["mp4"]).status_code == 403
    assert _upload(client, 999, sample_videos["mp4"]).status_code == 404
    assert not any(storage.incoming_dir(get_settings()).iterdir())  # temp uploads cleaned up


def test_inbox_scan(client: TestClient, db: Session, sample_videos: dict[str, Path]) -> None:
    s = _live_streamer(db, capture=False)
    inbox = storage.inbox_dir(get_settings())
    (inbox / str(s.id)).mkdir(exist_ok=True)
    (inbox / str(s.id) / "bolum1.mp4").write_bytes(sample_videos["mp4"].read_bytes())
    (inbox / str(s.id) / "notes.txt").write_text("x")
    (inbox / "unknown-folder").mkdir(exist_ok=True)

    result = client.post(f"{API}/inbox/scan").json()
    assert [r["title"] for r in result["imported"]] == ["bolum1"]
    assert {e["file"] for e in result["errors"]} == {f"{s.id}/notes.txt", "unknown-folder"}
    assert not (inbox / str(s.id) / "bolum1.mp4").exists()  # moved into storage
    (inbox / str(s.id) / "notes.txt").unlink()
    (inbox / "unknown-folder").rmdir()


def test_delete_recording_removes_files(client: TestClient, db: Session, sample_videos: dict[str, Path]) -> None:
    s = _live_streamer(db, capture=False)
    rec = _upload(client, s.id, sample_videos["mp4"]).json()
    path = storage.to_absolute(get_settings(), _session(db, rec["id"]).file_path)  # type: ignore[arg-type]
    assert client.delete(f"{API}/{rec['id']}").status_code == 204
    assert not path.exists() and client.get(f"{API}/{rec['id']}").status_code == 404

    active = RecordingSession(streamer_id=s.id, status=RecordingStatus.RECORDING)
    db.add(active)
    db.commit()
    assert client.delete(f"{API}/{active.id}").status_code == 409
    assert client.post(f"{API}/{active.id}/stop").status_code == 409  # no running process behind it


def test_system_info_and_live_endpoint_guards(client: TestClient, db: Session) -> None:
    info = client.get(f"{API}/system").json()
    assert info["ffmpeg_available"] is True and info["ytdlp_version"]
    assert ".mp4" in info["allowed_extensions"] and info["inbox_path"].endswith("recordings/inbox")
    s = _live_streamer(db, capture=False)
    assert client.post(f"{API}/live", json={"streamer_id": s.id}).status_code == 403


def test_capture_flag_requires_permission(client: TestClient, db: Session) -> None:
    body = {"name": "Cap", "platform": "twitch", "channel_url": "https://twitch.tv/cap", "live_capture_enabled": True}
    assert client.post("/api/v1/streamers", json=body).status_code == 422
    created = client.post("/api/v1/streamers", json=body | {"recording_permission_confirmed": True, "permission_notes": "ok"}).json()
    assert created["live_capture_enabled"] is True
    revoked = client.patch(f"/api/v1/streamers/{created['id']}", json={"recording_permission_confirmed": False}).json()
    assert revoked["live_capture_enabled"] is False  # revoking permission switches capture off
