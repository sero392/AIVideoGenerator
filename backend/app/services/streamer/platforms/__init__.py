"""Platform adapter registry, built from settings."""

from __future__ import annotations

from app.core.config import Settings
from app.models.enums import StreamPlatform
from app.services.streamer.platforms.base import ChannelRef, LiveStatus, PlatformAdapter, PlatformError
from app.services.streamer.platforms.kick import KickAdapter
from app.services.streamer.platforms.twitch import TwitchAdapter
from app.services.streamer.platforms.youtube import YouTubeAdapter

__all__ = ["ChannelRef", "LiveStatus", "PlatformAdapter", "PlatformError", "build_adapters"]


def build_adapters(settings: Settings) -> dict[StreamPlatform, PlatformAdapter]:
    """One adapter per supported platform. ``StreamPlatform.OTHER`` has none."""
    return {
        StreamPlatform.TWITCH: TwitchAdapter(
            settings.twitch_client_id,
            settings.twitch_client_secret.get_secret_value(),
            settings.twitch_poll_interval_seconds,
        ),
        StreamPlatform.KICK: KickAdapter(
            settings.kick_client_id,
            settings.kick_client_secret.get_secret_value(),
            settings.kick_poll_interval_seconds,
        ),
        StreamPlatform.YOUTUBE: YouTubeAdapter(
            settings.youtube_api_key.get_secret_value(),
            settings.youtube_poll_interval_seconds,
        ),
    }
