"""FFmpeg helpers (binary resolution, probing, remuxing) + video processing interface.

Phase 3 only needs lossless operations (probe, remux with ``-c copy``); cutting and
editing (phases 7-8) will implement :class:`VideoProcessor`.
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


class MediaError(Exception):
    """A file is not a usable video, or FFmpeg failed (user-facing message)."""


@lru_cache
def ffmpeg_path(binary: str = "ffmpeg") -> str | None:
    """PATH lookup first (or an explicit path), then the copy bundled by imageio-ffmpeg."""
    found = shutil.which(binary)
    if found:
        return found
    if binary != "ffmpeg":
        return None  # an explicit custom path was configured but does not exist
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001  (package missing or binary not downloaded)
        return None


def require_ffmpeg(binary: str = "ffmpeg") -> str:
    path = ffmpeg_path(binary)
    if not path:
        raise MediaError("FFmpeg bulunamadı (pip install -r requirements.txt).")
    return path


def opencv_installed() -> bool:
    return importlib.util.find_spec("cv2") is not None


@dataclass(slots=True)
class MediaInfo:
    duration_seconds: float | None
    has_video: bool
    has_audio: bool
    width: int | None = None
    height: int | None = None


_DURATION = re.compile(r"Duration:\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")
_VIDEO = re.compile(r"Stream #\S+.*?: Video: .*?(\d{2,5})x(\d{2,5})")


def probe(path: Path, ffmpeg: str) -> MediaInfo:
    """Read container info via ``ffmpeg -i`` (imageio-ffmpeg ships no ffprobe)."""
    proc = subprocess.run(  # noqa: S603  (fixed binary, path is ours)
        [ffmpeg, "-hide_banner", "-nostdin", "-i", str(path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    info = proc.stderr
    if "Invalid data found" in info or "moov atom not found" in info:
        raise MediaError("Dosya okunamadı; geçerli bir video dosyası değil ya da bozuk.")
    duration = None
    if m := _DURATION.search(info):
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    video = _VIDEO.search(info)
    return MediaInfo(
        duration_seconds=duration,
        has_video=bool(video) or ": Video:" in info,
        has_audio=": Audio:" in info,
        width=int(video.group(1)) if video else None,
        height=int(video.group(2)) if video else None,
    )


def is_mpegts(path: Path) -> bool:
    """MPEG-TS files start with 0x47 sync bytes every 188 bytes, whatever their extension.

    yt-dlp may name a live MPEG-TS capture ``.mp4``; browsers cannot play that.
    """
    try:
        with path.open("rb") as fh:
            head = fh.read(188 * 3 + 1)
    except OSError:
        return False
    return len(head) > 376 and head[0] == head[188] == head[376] == 0x47


def remux_to_mp4(src: Path, dst: Path, ffmpeg: str) -> None:
    """Lossless container change (no re-encoding) with the index at the front for web playback."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".remux.mp4")
    proc = subprocess.run(  # noqa: S603
        [ffmpeg, "-hide_banner", "-nostdin", "-y", "-i", str(src), "-map", "0:v?", "-map", "0:a?",
         "-c", "copy", "-movflags", "+faststart", str(tmp)],
        capture_output=True,
        text=True,
        timeout=6 * 3600,
    )
    if proc.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        tail = " ".join(proc.stderr.strip().splitlines()[-2:])[:300]
        raise MediaError(f"MP4'e dönüştürülemedi: {tail or 'bilinmeyen FFmpeg hatası'}")
    tmp.replace(dst)


class VideoProcessor(ABC):
    @abstractmethod
    def cut(self, source: Path, destination: Path, start: float, end: float) -> Path: ...

    @abstractmethod
    def extract_audio(self, source: Path, destination: Path) -> Path: ...

    @abstractmethod
    def generate_thumbnail(self, source: Path, destination: Path, at_seconds: float) -> Path: ...
