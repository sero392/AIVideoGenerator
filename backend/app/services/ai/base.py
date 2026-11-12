"""Provider-agnostic AI interfaces.

New providers (another local runtime, or a hosted API) implement these ABCs and
register in :mod:`app.services.ai.registry`. The runtime must never depend on a
paid/hosted API — local models are the default.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

ServiceState = Literal["ok", "unavailable", "disabled", "error"]


@dataclass(slots=True)
class ProviderHealth:
    provider: str
    status: ServiceState
    detail: str | None = None
    models: list[str] = field(default_factory=list)


@dataclass(slots=True)
class LLMResponse:
    model: str
    text: str
    raw: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """A text-generation backend (e.g. Ollama serving Qwen)."""

    name: str

    @abstractmethod
    async def health_check(self) -> ProviderHealth: ...

    @abstractmethod
    async def list_models(self) -> list[str]: ...

    @abstractmethod
    async def generate(self, prompt: str, *, model: str | None = None, options: dict[str, Any] | None = None) -> LLMResponse:
        ...


@dataclass(slots=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(slots=True)
class Transcript:
    language: str | None
    segments: list[TranscriptSegment]


class TranscriptionProvider(ABC):
    """Speech-to-text backend (e.g. faster-whisper)."""

    name: str

    @abstractmethod
    def health_check(self) -> ProviderHealth: ...

    @abstractmethod
    def transcribe(self, audio_path: Path, *, language: str | None = None) -> Transcript: ...
