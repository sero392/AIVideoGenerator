"""faster-whisper connector. The package is optional (requirements-ai.txt) and imported lazily."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.services.ai.base import ProviderHealth, Transcript, TranscriptionProvider


class FasterWhisperProvider(TranscriptionProvider):
    name = "faster-whisper"

    def __init__(self, model_size: str, device: str = "auto", compute_type: str = "int8") -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type

    @staticmethod
    def is_installed() -> bool:
        return importlib.util.find_spec("faster_whisper") is not None

    def health_check(self) -> ProviderHealth:
        if not self.is_installed():
            return ProviderHealth(self.name, "unavailable", "faster-whisper not installed (pip install -r requirements-ai.txt)")
        return ProviderHealth(self.name, "ok", f"Installed (model size: {self.model_size})")

    def transcribe(self, audio_path: Path, *, language: str | None = None) -> Transcript:
        raise NotImplementedError("Transcription is planned for roadmap phase 5 (Whisper integration).")
