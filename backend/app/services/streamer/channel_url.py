"""Channel URL validation and normalisation per platform.

Normalising (lower-case host, no ``www.``/``m.``, no query/fragment, no trailing
slash) makes the unique constraint on ``channel_url`` meaningful:
``https://www.Twitch.tv/foo/`` and ``https://twitch.tv/foo`` are the same channel.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from app.models.enums import StreamPlatform

_PLATFORM_HOSTS: dict[StreamPlatform, str] = {
    StreamPlatform.TWITCH: "twitch.tv",
    StreamPlatform.YOUTUBE: "youtube.com",
    StreamPlatform.KICK: "kick.com",
}

_SIMPLE_CHANNEL = re.compile(r"^/[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}$")
_YOUTUBE_CHANNEL = re.compile(r"^/(@[A-Za-z0-9_.-]{1,100}|channel/UC[A-Za-z0-9_-]{22}|c/[^/]{1,100}|user/[^/]{1,100})$")

_PLATFORM_EXAMPLES: dict[StreamPlatform, str] = {
    StreamPlatform.TWITCH: "https://twitch.tv/kanaladi",
    StreamPlatform.YOUTUBE: "https://youtube.com/@kanaladi",
    StreamPlatform.KICK: "https://kick.com/kanaladi",
}


def normalize_channel_url(platform: StreamPlatform, raw_url: str) -> str:
    """Return the canonical URL or raise ``ValueError`` with a user-facing message."""
    url = raw_url.strip()
    if len(url) > 500:
        raise ValueError("Kanal adresi en fazla 500 karakter olabilir.")
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise ValueError("Kanal adresi https:// ile başlamalıdır.")
    host = (parts.hostname or "").lower()
    if not host or parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError("Geçerli bir kanal adresi girin.")
    for prefix in ("www.", "m."):
        if host.startswith(prefix):
            host = host[len(prefix) :]
            break
    path = parts.path.rstrip("/")

    expected_host = _PLATFORM_HOSTS.get(platform)
    if expected_host is None:  # StreamPlatform.OTHER: any https URL with a host
        if "." not in host:
            raise ValueError("Geçerli bir kanal adresi girin.")
        return f"https://{host}{path}"

    example = _PLATFORM_EXAMPLES[platform]
    if host != expected_host:
        raise ValueError(f"Bu platform için adres {expected_host} olmalıdır (ör. {example}).")
    pattern = _YOUTUBE_CHANNEL if platform is StreamPlatform.YOUTUBE else _SIMPLE_CHANNEL
    if not pattern.match(path):
        raise ValueError(f"Kanal adresi geçersiz. Örnek: {example}")
    if platform is not StreamPlatform.YOUTUBE:
        path = path.lower()  # Twitch/Kick channel names are case-insensitive
    return f"https://{host}{path}"
