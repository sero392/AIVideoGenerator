"""Importing this package registers every model on ``Base.metadata``."""

from app.models.ai_model import AIModel
from app.models.clip import Clip
from app.models.enums import (
    AIProviderType,
    ClipStatus,
    RecordingStatus,
    StreamPlatform,
    YoutubeVideoStatus,
)
from app.models.recording import RecordingSession
from app.models.streamer import Streamer
from app.models.system_setting import SystemSetting
from app.models.youtube_video import YoutubeVideo

__all__ = [
    "AIModel",
    "AIProviderType",
    "Clip",
    "ClipStatus",
    "RecordingSession",
    "RecordingStatus",
    "StreamPlatform",
    "Streamer",
    "SystemSetting",
    "YoutubeVideo",
    "YoutubeVideoStatus",
]
