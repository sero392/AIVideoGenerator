"""Video processing interface + tool availability checks (implementation: phases 7-8)."""

from __future__ import annotations

import importlib.util
import shutil
from abc import ABC, abstractmethod
from pathlib import Path


def ffmpeg_path(binary: str) -> str | None:
    return shutil.which(binary)


def opencv_installed() -> bool:
    return importlib.util.find_spec("cv2") is not None


class VideoProcessor(ABC):
    @abstractmethod
    def cut(self, source: Path, destination: Path, start: float, end: float) -> Path: ...

    @abstractmethod
    def extract_audio(self, source: Path, destination: Path) -> Path: ...

    @abstractmethod
    def generate_thumbnail(self, source: Path, destination: Path, at_seconds: float) -> Path: ...
