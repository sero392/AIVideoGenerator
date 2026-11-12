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
