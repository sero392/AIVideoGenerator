"""Where recording files live and how they are named."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from app.core.config import Settings
from app.core.paths import StorageArea, resolve_within, sanitize_filename, storage_path

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm", ".ts", ".flv", ".m4v"}
INBOX_DIR = "inbox"
INCOMING_DIR = ".incoming"


def recordings_root(settings: Settings) -> Path:
    root = storage_path(settings, StorageArea.RECORDINGS)
    root.mkdir(parents=True, exist_ok=True)
    return root


def streamer_dir_name(streamer_id: int, name: str) -> str:
    try:
        slug = sanitize_filename(name, max_length=60)
    except Exception:  # noqa: BLE001  (name made only of unsafe characters)
        slug = "streamer"
    return f"{slug}-{streamer_id}"


def new_base_path(settings: Settings, streamer_id: int, streamer_name: str, session_id: int, when: datetime) -> Path:
    """Extension-less, collision-free base path, e.g. storage/recordings/apex-2/20261116-161346-7.

    SQLite may reuse the id of a deleted last row, so the name is checked against
    existing files: a capture tool must never find (and skip or overwrite) a file
    that belongs to another recording.
    """
    directory = recordings_root(settings) / streamer_dir_name(streamer_id, streamer_name)
    directory.mkdir(parents=True, exist_ok=True)
    stem = f"{when:%Y%m%d-%H%M%S}-{session_id}"
    base, n = directory / stem, 1
    while any(directory.glob(f"{base.name}.*")):
        n += 1
        base = directory / f"{stem}-{n}"
    return base


def to_relative(settings: Settings, path: Path) -> str:
    return path.resolve().relative_to(recordings_root(settings)).as_posix()


def to_absolute(settings: Settings, relative: str) -> Path:
    """Resolve a DB path, refusing anything outside storage/recordings."""
    return resolve_within(recordings_root(settings), *relative.split("/"))


def free_gb(settings: Settings) -> float:
    return shutil.disk_usage(recordings_root(settings)).free / 1024**3


def inbox_dir(settings: Settings) -> Path:
    path = recordings_root(settings) / INBOX_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def incoming_dir(settings: Settings) -> Path:
    path = recordings_root(settings) / INCOMING_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path
