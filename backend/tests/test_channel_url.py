from __future__ import annotations

import pytest

from app.models.enums import StreamPlatform as P
from app.services.streamer.channel_url import normalize_channel_url


@pytest.mark.parametrize(
    ("platform", "raw", "expected"),
    [
        (P.TWITCH, "https://www.Twitch.tv/SomeStreamer/", "https://twitch.tv/somestreamer"),
        (P.TWITCH, " https://m.twitch.tv/abc_123?ref=x#y ", "https://twitch.tv/abc_123"),
        (P.KICK, "https://kick.com/Foo", "https://kick.com/foo"),
        (P.YOUTUBE, "https://www.youtube.com/@MyChannel", "https://youtube.com/@MyChannel"),
        (P.YOUTUBE, "https://youtube.com/channel/UCabcdefghijklmnopqrstuv", "https://youtube.com/channel/UCabcdefghijklmnopqrstuv"),
        (P.OTHER, "https://www.example.org/live/", "https://example.org/live"),
    ],
)
def test_normalizes(platform: P, raw: str, expected: str) -> None:
    assert normalize_channel_url(platform, raw) == expected


@pytest.mark.parametrize(
    ("platform", "raw", "message_part"),
    [
        (P.TWITCH, "http://twitch.tv/foo", "https://"),
        (P.TWITCH, "https://kick.com/foo", "twitch.tv"),
        (P.TWITCH, "https://twitch.tv/", "geçersiz"),
        (P.TWITCH, "https://twitch.tv/foo/videos", "geçersiz"),
        (P.TWITCH, "https://evil.twitch.tv.attacker.com/foo", "twitch.tv"),
        (P.YOUTUBE, "https://youtube.com/watch?v=abc", "geçersiz"),
        (P.KICK, "https://user:pass@kick.com/foo", "Geçerli"),
        (P.OTHER, "https://localhost/foo", "Geçerli"),
        (P.OTHER, "javascript:alert(1)", "https://"),
    ],
)
def test_rejects(platform: P, raw: str, message_part: str) -> None:
    with pytest.raises(ValueError, match=message_part):
        normalize_channel_url(platform, raw)
