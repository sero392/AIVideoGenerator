"""Adapters against mocked HTTP (no network). Response shapes follow the platforms' API docs."""

from __future__ import annotations

import httpx
import pytest

from app.services.streamer.platforms import ChannelRef, LiveStatus, PlatformError
from app.services.streamer.platforms.kick import KickAdapter
from app.services.streamer.platforms.twitch import TwitchAdapter
from app.services.streamer.platforms.youtube import YouTubeAdapter

UC_ID = "UC" + "a" * 22


def transport(handler) -> httpx.MockTransport:  # type: ignore[no-untyped-def]
    return httpx.MockTransport(handler)


# --- Twitch -------------------------------------------------------------------
async def test_twitch_live_and_offline_batch() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.host == "id.twitch.tv":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer tok"
        assert request.headers["Client-Id"] == "cid"
        assert sorted(request.url.params.get_list("user_login")) == ["alpha", "beta"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "s1",
                        "user_id": "u1",
                        "user_login": "alpha",
                        "type": "live",
                        "title": "Hello",
                        "viewer_count": 42,
                        "started_at": "2026-11-16T10:00:00Z",
                    }
                ]
            },
        )

    adapter = TwitchAdapter("cid", "secret", 120, transport=transport(handler))
    refs = [ChannelRef(1, "https://twitch.tv/alpha"), ChannelRef(2, "https://twitch.tv/beta")]
    result = await adapter.check(refs)
    assert isinstance(result[1], LiveStatus) and result[1].is_live and result[1].viewer_count == 42
    assert result[1].started_at is not None and result[1].resolved_channel_id == "u1"
    assert isinstance(result[2], LiveStatus) and not result[2].is_live

    await adapter.check(refs)
    assert sum(1 for c in calls if c.url.host == "id.twitch.tv") == 1  # token cached


async def test_twitch_rejected_credentials() -> None:
    adapter = TwitchAdapter("cid", "bad", 120, transport=transport(lambda r: httpx.Response(401, text="secret-echo")))
    with pytest.raises(PlatformError, match="reddedildi") as exc:
        await adapter.check([ChannelRef(1, "https://twitch.tv/a")])
    assert "secret-echo" not in str(exc.value)


async def test_twitch_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("blocked", request=request)

    with pytest.raises(PlatformError, match="bağlanılamadı"):
        await TwitchAdapter("c", "s", 120, transport=transport(handler)).check([ChannelRef(1, "https://twitch.tv/a")])


def test_configured_flags() -> None:
    assert not TwitchAdapter("", "", 120).is_configured()
    assert KickAdapter("id", "secret", 120).is_configured()
    assert not YouTubeAdapter("", 300).is_configured()


# --- Kick ---------------------------------------------------------------------
async def test_kick_channels() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "id.kick.com":
            return httpx.Response(200, json={"access_token": "kt", "expires_in": 7200})
        assert request.url.params.get_list("slug") == ["live1", "off1", "missing"]
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "slug": "live1",
                        "broadcaster_user_id": 7,
                        "stream_title": "Kick live",
                        "stream": {"is_live": True, "viewer_count": 5, "start_time": "2026-11-16T09:00:00Z"},
                    },
                    {"slug": "off1", "broadcaster_user_id": 8, "stream_title": "old", "stream": {"is_live": False}},
                ]
            },
        )

    adapter = KickAdapter("id", "secret", 120, transport=transport(handler))
    result = await adapter.check(
        [ChannelRef(1, "https://kick.com/live1"), ChannelRef(2, "https://kick.com/off1"), ChannelRef(3, "https://kick.com/missing")]
    )
    assert isinstance(result[1], LiveStatus) and result[1].is_live and result[1].title == "Kick live"
    assert isinstance(result[2], LiveStatus) and not result[2].is_live and result[2].title is None
    assert isinstance(result[3], PlatformError)


# --- YouTube ------------------------------------------------------------------
FEED = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">
  <entry><yt:videoId>LIVEvid0001</yt:videoId></entry>
  <entry><yt:videoId>OLDvid00002</yt:videoId></entry>
</feed>"""


def youtube_handler(*, live: bool, quota: bool = False, calls: list | None = None):  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        if calls is not None:
            calls.append(request)
        path = request.url.path
        if path.endswith("/channels"):
            assert request.url.params["forHandle"] == "@MyChannel"
            assert request.url.params["key"] == "ykey"
            return httpx.Response(200, json={"items": [{"id": UC_ID}]})
        if path.endswith("/feeds/videos.xml"):
            assert request.url.params["channel_id"] == UC_ID
            return httpx.Response(200, content=FEED.encode())
        if path.endswith("/videos"):
            if quota:
                return httpx.Response(403, json={"error": {"errors": [{"reason": "quotaExceeded"}]}})
            assert request.url.params["id"] == "LIVEvid0001,OLDvid00002"
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "LIVEvid0001",
                            "snippet": {"title": "Canlı!", "liveBroadcastContent": "live" if live else "none"},
                            "liveStreamingDetails": {"actualStartTime": "2026-11-16T11:00:00Z", "concurrentViewers": "321"},
                        },
                        {"id": "OLDvid00002", "snippet": {"title": "eski", "liveBroadcastContent": "none"}},
                    ]
                },
            )
        return httpx.Response(404)

    return handler


async def test_youtube_resolves_handle_and_detects_live() -> None:
    adapter = YouTubeAdapter("ykey", 300, transport=transport(youtube_handler(live=True)))
    result = (await adapter.check([ChannelRef(1, "https://youtube.com/@MyChannel")]))[1]
    assert isinstance(result, LiveStatus) and result.is_live
    assert result.viewer_count == 321
    assert result.stream_url == "https://www.youtube.com/watch?v=LIVEvid0001"
    assert result.resolved_channel_id == UC_ID


async def test_youtube_uses_cached_channel_id() -> None:
    calls: list[httpx.Request] = []
    adapter = YouTubeAdapter("ykey", 300, transport=transport(youtube_handler(live=False, calls=calls)))
    result = (await adapter.check([ChannelRef(1, "https://youtube.com/@MyChannel", platform_channel_id=UC_ID)]))[1]
    assert isinstance(result, LiveStatus) and not result.is_live
    assert not any(c.url.path.endswith("/channels") for c in calls)


async def test_youtube_checks_all_feed_entries_and_known_stream() -> None:
    feed_ids = [f"vid{i:08d}" for i in range(15)]
    feed = (
        '<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns="http://www.w3.org/2005/Atom">'
        + "".join(f"<entry><yt:videoId>{v}</yt:videoId></entry>" for v in feed_ids)
        + "</feed>"
    )
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/feeds/videos.xml"):
            return httpx.Response(200, content=feed.encode())
        ids = request.url.params["id"].split(",")
        seen.extend(ids)
        # Only the 12th feed entry is live (would be missed if only the first 5 were checked)
        return httpx.Response(
            200,
            json={"items": [{"id": v, "snippet": {"title": v, "liveBroadcastContent": "live" if v == "vid00000011" else "none"}} for v in ids]},
        )

    adapter = YouTubeAdapter("ykey", 300, transport=transport(handler))
    ref = ChannelRef(1, "https://youtube.com/@x", platform_channel_id=UC_ID, known_stream_id="oldLIVE0001")
    result = (await adapter.check([ref]))[1]
    assert isinstance(result, LiveStatus) and result.is_live and result.stream_id == "vid00000011"
    assert seen[0] == "oldLIVE0001" and set(feed_ids) <= set(seen)


async def test_youtube_quota_and_unsupported_url() -> None:
    adapter = YouTubeAdapter("ykey", 300, transport=transport(youtube_handler(live=True, quota=True)))
    with pytest.raises(PlatformError, match="kota"):
        await adapter.check([ChannelRef(1, "https://youtube.com/@MyChannel")])

    adapter = YouTubeAdapter("ykey", 300, transport=transport(youtube_handler(live=True)))
    result = await adapter.check([ChannelRef(2, "https://youtube.com/c/Legacy")])
    assert isinstance(result[2], PlatformError) and "@handle" in str(result[2])
