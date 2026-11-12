"""Safe file-path handling for everything under the storage directory."""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path

from app.core.config import Settings
from app.core.exceptions import UnsafePathError


class StorageArea(str, Enum):
    RECORDINGS = "recordings"
    CLIPS = "clips"
    PUBLISHED = "published"
    THUMBNAILS = "thumbnails"


_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str, *, max_length: int = 120) -> str:
    """Turn arbitrary text (e.g. a streamer name) into a safe file name component."""
    cleaned = _UNSAFE_CHARS.sub("_", name).strip("._")
    cleaned = cleaned[:max_length]
    if not cleaned:
        raise UnsafePathError("File name is empty after sanitization.")
    return cleaned


def resolve_within(base: Path, *parts: str) -> Path:
    """Join ``parts`` onto ``base`` and guarantee the result stays inside ``base``.

    Rejects absolute paths and ``..`` traversal (including via symlinks).
    """
    base_resolved = base.resolve()
    candidate = base_resolved.joinpath(*parts).resolve()
    if candidate != base_resolved and base_resolved not in candidate.parents:
        raise UnsafePathError("Path escapes the allowed storage directory.", details={"path": "/".join(parts)})
    return candidate


def storage_path(settings: Settings, area: StorageArea, *parts: str) -> Path:
    return resolve_within(settings.storage_dir / area.value, *parts)


def ensure_storage_dirs(settings: Settings) -> None:
    for area in StorageArea:
        (settings.storage_dir / area.value).mkdir(parents=True, exist_ok=True)
    (settings.storage_dir / "database").mkdir(parents=True, exist_ok=True)
