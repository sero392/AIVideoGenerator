"""Importing this package registers every model on ``Base.metadata``."""

from app.models.ai_model import AIModel
from app.models.clip import Clip
from app.models.enums import (
    AIProviderType,
    ClipStatus,
    RecordingSource,
    RecordingStatus,
    StreamEventType,
    StreamPlatform,
    TrackingState,
    YoutubeVideoStatus,
)
from app.models.recording import RecordingSession
from app.models.streamer import Streamer
from app.models.system_setting import SystemSetting
from app.models.tracking import StreamEvent, StreamStatus, TrackingWindow
from app.models.youtube_video import YoutubeVideo

__all__ = [
    "AIModel",
    "AIProviderType",
    "Clip",
    "ClipStatus",
    "RecordingSession",
    "RecordingSource",
    "RecordingStatus",
    "StreamEvent",
    "StreamEventType",
    "StreamPlatform",
    "StreamStatus",
    "Streamer",
    "SystemSetting",
    "TrackingState",
    "TrackingWindow",
    "YoutubeVideo",
    "YoutubeVideoStatus",
]
