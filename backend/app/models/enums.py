"""Status / type enums. Stored as plain strings (no native DB enums) for SQLite + Alembic friendliness."""

from __future__ import annotations

from enum import Enum


class StreamPlatform(str, Enum):
    TWITCH = "twitch"
    YOUTUBE = "youtube"
    KICK = "kick"
    OTHER = "other"


class RecordingStatus(str, Enum):
    SCHEDULED = "scheduled"
    RECORDING = "recording"
    PROCESSING = "processing"  # remuxing / probing after capture or import
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ClipStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class YoutubeVideoStatus(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    UPLOADING = "uploading"
    PUBLISHED = "published"
    FAILED = "failed"


class AIProviderType(str, Enum):
    OLLAMA = "ollama"
    FASTER_WHISPER = "faster-whisper"


class TrackingState(str, Enum):
    PENDING = "pending"  # never checked yet
    LIVE = "live"
    OFFLINE = "offline"
    OUTSIDE_SCHEDULE = "outside_schedule"  # active, but no tracking window right now
    INACTIVE = "inactive"  # streamer deactivated
    NOT_CONFIGURED = "not_configured"  # platform API credentials missing
    UNSUPPORTED = "unsupported"  # platform has no adapter (e.g. "other")
    ERROR = "error"


class StreamEventType(str, Enum):
    WENT_LIVE = "went_live"
    WENT_OFFLINE = "went_offline"


class RecordingSource(str, Enum):
    LIVE_CAPTURE = "live_capture"  # recorded from a live stream (opt-in per streamer)
    IMPORT = "import"  # file provided by the streamer (upload or inbox folder)
