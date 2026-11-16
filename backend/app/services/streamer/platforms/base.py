"""Platform adapter contract for live-status checks.

Adapters only use official, documented platform APIs with the operator's own
credentials. They never scrape pages or download stream content.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

import httpx

from app.models.enums import StreamPlatform

HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class PlatformError(Exception):
    """A user-facing problem with one channel or the platform API (no secrets in the message)."""


@dataclass(slots=True)
class ChannelRef:
    streamer_id: int
    channel_url: str
    platform_channel_id: str | None = None
    # Platform id of the stream we last saw live; adapters re-check it so a long
    # stream is not lost when it drops out of "recent videos" listings.
    known_stream_id: str | None = None

    @property
    def path(self) -> str:
        return urlsplit(self.channel_url).path.strip("/")


@dataclass(slots=True)
class LiveStatus:
    is_live: bool
    title: str | None = None
    viewer_count: int | None = None
    started_at: datetime | None = None
    stream_id: str | None = None
    stream_url: str | None = None
    # Set when the adapter resolved a stable platform id (cached on the streamer).
    resolved_channel_id: str | None = None


CheckResult = dict[int, LiveStatus | PlatformError]


class PlatformAdapter(ABC):
    platform: StreamPlatform
    #: Env vars the operator must set, shown in the UI when unconfigured.
    required_settings: tuple[str, ...] = ()

    def __init__(self, poll_interval_seconds: int, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.poll_interval_seconds = poll_interval_seconds
        self._transport = transport  # injectable for tests

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=HTTP_TIMEOUT, transport=self._transport)

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    async def check(self, channels: list[ChannelRef]) -> CheckResult:
        """Return a status or a ``PlatformError`` for every channel (keyed by streamer id).

        May raise ``PlatformError`` when the whole platform call fails.
        """


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def chunks(items: list, size: int) -> list[list]:  # type: ignore[type-arg]
    return [items[i : i + size] for i in range(0, len(items), size)]


class AppTokenCache:
    """In-memory OAuth client-credentials token with early refresh."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at = 0.0

    def get(self) -> str | None:
        return self._token if self._token and time.monotonic() < self._expires_at - 60 else None

    def set(self, token: str, expires_in: float) -> None:
        self._token = token
        self._expires_at = time.monotonic() + max(expires_in, 60)

    def clear(self) -> None:
        self._token = None
        self._expires_at = 0.0


def raise_for_platform(response: httpx.Response, platform: str) -> None:
    """Map HTTP failures to user-facing errors without echoing response bodies (may contain tokens)."""
    if response.is_success:
        return
    if response.status_code in (401, 403):
        raise PlatformError(f"{platform} API kimlik bilgileri reddedildi (HTTP {response.status_code}).")
    if response.status_code == 429:
        raise PlatformError(f"{platform} API istek sınırına ulaşıldı (HTTP 429), sonraki turda tekrar denenecek.")
    raise PlatformError(f"{platform} API hatası (HTTP {response.status_code}).")
