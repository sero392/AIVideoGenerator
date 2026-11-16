"""YouTube adapter: quota-friendly live detection with the Data API v3.

1. Resolve the channel id once (``channels.list`` forHandle/forUsername, 1 unit) and cache it.
2. Read the channel's public Atom feed (YouTube's own feed, no quota): its ~15 newest videos,
   which include current live broadcasts. The stream seen live last time is always re-checked too.
3. ``videos.list`` (1 unit per 50 ids, batched across channels) -> ``liveBroadcastContent == "live"``.

Limitation: a stream that started before the channel's 15 most recent uploads (e.g. a
months-long 24/7 stream first seen after many newer uploads) is not discovered.

This avoids ``search.list`` (100 units per call), so a 5-minute poll costs
~290 units/day per channel against the default 10,000 daily quota.
Docs: https://developers.google.com/youtube/v3/docs/videos/list
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

import httpx

from app.models.enums import StreamPlatform
from app.services.streamer.platforms.base import (
    ChannelRef,
    CheckResult,
    LiveStatus,
    PlatformAdapter,
    PlatformError,
    chunks,
    parse_datetime,
    raise_for_platform,
)

API_BASE = "https://www.googleapis.com/youtube/v3"
FEED_URL = "https://www.youtube.com/feeds/videos.xml"
# The feed returns ~15 entries; checking all of them still costs 1 unit per 50 ids.
RECENT_VIDEOS_PER_CHANNEL = 15
_CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
_ATOM = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


class YouTubeAdapter(PlatformAdapter):
    platform = StreamPlatform.YOUTUBE
    required_settings = ("YOUTUBE_API_KEY",)

    def __init__(self, api_key: str, poll_interval_seconds: int, transport=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(poll_interval_seconds, transport)
        self._api_key = api_key

    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def _api(self, client: httpx.AsyncClient, resource: str, params: dict[str, str]) -> dict:
        response = await client.get(f"{API_BASE}/{resource}", params={**params, "key": self._api_key})
        if response.status_code == 403 and "quota" in response.text.lower():
            raise PlatformError("YouTube API günlük kotası doldu; yarın otomatik devam edecek.")
        raise_for_platform(response, "YouTube")
        return response.json()

    async def _resolve_channel_id(self, client: httpx.AsyncClient, ref: ChannelRef) -> str:
        if ref.platform_channel_id and _CHANNEL_ID.match(ref.platform_channel_id):
            return ref.platform_channel_id
        path = ref.path
        if path.startswith("channel/"):
            return path.split("/", 1)[1]
        if path.startswith("@"):
            params = {"part": "id", "forHandle": path}
        elif path.startswith("user/"):
            params = {"part": "id", "forUsername": path.split("/", 1)[1]}
        else:
            raise PlatformError("Bu YouTube adres biçimi çözümlenemiyor; kanalın @handle adresini kullanın.")
        items = (await self._api(client, "channels", params)).get("items") or []
        if not items:
            raise PlatformError("YouTube'da bu kanal bulunamadı.")
        return str(items[0]["id"])

    async def _recent_video_ids(self, client: httpx.AsyncClient, channel_id: str) -> list[str]:
        response = await client.get(FEED_URL, params={"channel_id": channel_id})
        if response.status_code == 404:
            raise PlatformError("YouTube kanal akışı bulunamadı.")
        raise_for_platform(response, "YouTube")
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise PlatformError("YouTube kanal akışı okunamadı.") from exc
        ids = [el.text for el in root.findall("atom:entry/yt:videoId", _ATOM) if el.text]
        return ids[:RECENT_VIDEOS_PER_CHANNEL]

    async def check(self, channels: list[ChannelRef]) -> CheckResult:
        result: CheckResult = {}
        resolved: dict[int, str] = {}
        candidates: dict[str, int] = {}  # video id -> streamer id
        try:
            async with self.client() as client:
                for ref in channels:
                    try:
                        channel_id = await self._resolve_channel_id(client, ref)
                        resolved[ref.streamer_id] = channel_id
                        video_ids = await self._recent_video_ids(client, channel_id)
                        if ref.known_stream_id:
                            video_ids.insert(0, ref.known_stream_id)
                        for video_id in video_ids:
                            candidates.setdefault(video_id, ref.streamer_id)
                    except PlatformError as exc:
                        result[ref.streamer_id] = exc

                live: dict[int, dict] = {}
                for batch in chunks(list(candidates), 50):
                    data = await self._api(
                        client, "videos", {"part": "snippet,liveStreamingDetails", "id": ",".join(batch), "maxResults": "50"}
                    )
                    for video in data.get("items", []):
                        streamer_id = candidates.get(video.get("id", ""))
                        snippet = video.get("snippet") or {}
                        details = video.get("liveStreamingDetails") or {}
                        if streamer_id is not None and snippet.get("liveBroadcastContent") == "live" and not details.get("actualEndTime"):
                            live.setdefault(streamer_id, video)
        except httpx.HTTPError as exc:
            raise PlatformError(f"YouTube API'ye bağlanılamadı ({type(exc).__name__}).") from exc

        for streamer_id, channel_id in resolved.items():
            video = live.get(streamer_id)
            if video is None:
                result[streamer_id] = LiveStatus(is_live=False, resolved_channel_id=channel_id)
                continue
            details = video.get("liveStreamingDetails") or {}
            viewers = details.get("concurrentViewers")
            result[streamer_id] = LiveStatus(
                is_live=True,
                title=(video.get("snippet") or {}).get("title"),
                viewer_count=int(viewers) if str(viewers).isdigit() else None,
                started_at=parse_datetime(details.get("actualStartTime")),
                stream_id=video["id"],
                stream_url=f"https://www.youtube.com/watch?v={video['id']}",
                resolved_channel_id=channel_id,
            )
        return result
