from __future__ import annotations

import logging
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import RecordingNotPermittedError, UnsafePathError
from app.core.logging import RedactingFilter, redact
from app.core.paths import resolve_within, sanitize_filename
from app.models import StreamPlatform, Streamer
from app.schemas.streamer import StreamerCreate
from app.services.ai.ollama_provider import OllamaProvider
from app.services.streamer.base import ensure_recording_permitted


def test_cors_origins_parsed() -> None:
    s = Settings(cors_origins=" http://a.test , http://b.test ,")
    assert s.cors_origin_list == ["http://a.test", "http://b.test"]


def test_secret_not_in_repr() -> None:
    s = Settings(youtube_client_id="id", youtube_client_secret="super-secret-value")
    assert "super-secret-value" not in repr(s)
    assert s.youtube_oauth_configured


@pytest.mark.parametrize(
    "text",
    [
        "client_secret=abc123",
        'token: "abc123"',
        "Authorization: Bearer abc123",
        "api_key=abc123&x=1",
        "GET https://www.googleapis.com/youtube/v3/videos?part=snippet&key=abc123",
        "GET https://x.test/v1?key=abc123&id=1",
    ],
)
def test_redaction(text: str) -> None:
    assert "abc123" not in redact(text)


def test_redacting_filter_on_record() -> None:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "refresh_token=%s", ("xyz789",), None)
    RedactingFilter().filter(record)
    assert "xyz789" not in record.getMessage()


def test_resolve_within_blocks_traversal(tmp_path: Path) -> None:
    assert resolve_within(tmp_path, "a", "b.mp4") == (tmp_path / "a" / "b.mp4").resolve()
    with pytest.raises(UnsafePathError):
        resolve_within(tmp_path, "..", "etc", "passwd")
    with pytest.raises(UnsafePathError):
        resolve_within(tmp_path, "/etc/passwd")


def test_sanitize_filename() -> None:
    assert sanitize_filename("../Yayıncı Adı!") == "Yay_nc_Ad"
    with pytest.raises(UnsafePathError):
        sanitize_filename("../..")


def test_recording_requires_permission() -> None:
    streamer = Streamer(name="S", platform=StreamPlatform.TWITCH, channel_url="https://twitch.tv/s", is_active=True)
    streamer.recording_permission_confirmed = False
    with pytest.raises(RecordingNotPermittedError):
        ensure_recording_permitted(streamer)
    streamer.recording_permission_confirmed = True
    ensure_recording_permitted(streamer)


def test_streamer_schema_validation() -> None:
    ok = StreamerCreate(name="  Foo ", platform="twitch", channel_url="https://twitch.tv/foo")
    assert ok.name == "Foo"
    with pytest.raises(ValidationError):
        StreamerCreate(name="   ", platform="twitch", channel_url="https://twitch.tv/foo")
    with pytest.raises(ValidationError):
        StreamerCreate(name="x", platform="myspace", channel_url="https://x.test")
    with pytest.raises(ValidationError):  # unknown fields are rejected
        StreamerCreate(name="x", platform="twitch", channel_url="https://twitch.tv/x", is_admin=True)


async def test_ollama_provider_with_mock_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
        if request.url.path == "/api/generate":
            return httpx.Response(200, json={"model": "qwen2.5:7b", "response": "merhaba"})
        return httpx.Response(404)

    provider = OllamaProvider("http://ollama.test", "qwen2.5:7b", transport=httpx.MockTransport(handler))
    health = await provider.health_check()
    assert health.status == "ok" and health.models == ["qwen2.5:7b"]
    assert (await provider.generate("selam")).text == "merhaba"


async def test_ollama_provider_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    provider = OllamaProvider("http://ollama.test", "qwen2.5:7b", transport=httpx.MockTransport(handler))
    assert (await provider.health_check()).status == "unavailable"
