"""Recording permission guard.

Platform adapters (live status via official APIs) live in
:mod:`app.services.streamer.platforms`.
"""

from __future__ import annotations

from app.core.exceptions import RecordingNotPermittedError
from app.models import Streamer


def ensure_recording_permitted(streamer: Streamer) -> None:
    """Hard gate called by the recorder before any capture starts."""
    if not streamer.is_active:
        raise RecordingNotPermittedError(f"Streamer '{streamer.name}' is not active.")
    if not streamer.recording_permission_confirmed:
        raise RecordingNotPermittedError(
            f"Recording permission for '{streamer.name}' has not been confirmed. "
            "Only record streams whose owners allow it and whose platform terms permit it."
        )
