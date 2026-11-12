"""Platform adapter interface + the recording permission guard.

Each platform (Twitch, YouTube, Kick...) will get an adapter that only uses
official/permitted APIs. Nothing here records anything yet (roadmap phase 2).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.exceptions import RecordingNotPermittedError
from app.models import Streamer


@dataclass(slots=True)
class LiveStatus:
    is_live: bool
    title: str | None = None
    viewer_count: int | None = None


class StreamPlatformAdapter(ABC):
    platform: str

    @abstractmethod
    async def get_live_status(self, channel_url: str) -> LiveStatus: ...


def ensure_recording_permitted(streamer: Streamer) -> None:
    """Hard gate called by the recorder before any capture starts."""
    if not streamer.is_active:
        raise RecordingNotPermittedError(f"Streamer '{streamer.name}' is not active.")
    if not streamer.recording_permission_confirmed:
        raise RecordingNotPermittedError(
            f"Recording permission for '{streamer.name}' has not been confirmed. "
            "Only record streams whose owners allow it and whose platform terms permit it."
        )
