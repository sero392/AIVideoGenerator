"""Recorder interface (implementation: roadmap phase 3)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models import RecordingSession, Streamer


class StreamRecorder(ABC):
    @abstractmethod
    async def start(self, streamer: Streamer) -> RecordingSession:
        """Must call ``ensure_recording_permitted(streamer)`` before capturing."""

    @abstractmethod
    async def stop(self, session: RecordingSession) -> RecordingSession: ...
