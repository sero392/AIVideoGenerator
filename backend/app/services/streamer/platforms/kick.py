"""Kick public API adapter (app access token, GET /public/v1/channels?slug=...).

Docs: https://docs.kick.com (OpenAPI: https://api.kick.com/swagger/doc.yaml)

NOTE: The response fields used here (``slug``, ``stream_title``, ``stream.is_live``,
``stream.viewer_count``, ``stream.start_time``) could not be verified against the
live spec from the development network; parsing is defensive and covered by tests
with recorded-shape fixtures. Verify once Kick credentials are available.
"""

from __future__ import annotations

import httpx

from app.models.enums import StreamPlatform
from app.services.streamer.platforms.base import (
    AppTokenCache,
    ChannelRef,
    CheckResult,
    LiveStatus,
    PlatformAdapter,
    PlatformError,
    chunks,
    parse_datetime,
    raise_for_platform,
)

TOKEN_URL = "https://id.kick.com/oauth/token"
CHANNELS_URL = "https://api.kick.com/public/v1/channels"
MAX_SLUGS_PER_REQUEST = 50


class KickAdapter(PlatformAdapter):
    platform = StreamPlatform.KICK
    required_settings = ("KICK_CLIENT_ID", "KICK_CLIENT_SECRET")

    def __init__(self, client_id: str, client_secret: str, poll_interval_seconds: int, transport=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(poll_interval_seconds, transport)
        self._client_id = client_id
        self._client_secret = client_secret
        self._token = AppTokenCache()

    def is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        if token := self._token.get():
            return token
        response = await client.post(
            TOKEN_URL,
            data={"client_id": self._client_id, "client_secret": self._client_secret, "grant_type": "client_credentials"},
        )
        raise_for_platform(response, "Kick")
        data = response.json()
        self._token.set(data["access_token"], float(data.get("expires_in", 3600)))
        return data["access_token"]

    async def check(self, channels: list[ChannelRef]) -> CheckResult:
        by_slug = {c.path.lower(): c for c in channels}
        found: dict[str, dict] = {}
        try:
            async with self.client() as client:
                token = await self._access_token(client)
                for batch in chunks(list(by_slug), MAX_SLUGS_PER_REQUEST):
                    response = await client.get(
                        CHANNELS_URL,
                        params=[("slug", slug) for slug in batch],
                        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                    )
                    if response.status_code == 401:
                        self._token.clear()
                    raise_for_platform(response, "Kick")
                    for channel in response.json().get("data", []) or []:
                        found[str(channel.get("slug", "")).lower()] = channel
        except httpx.HTTPError as exc:
            raise PlatformError(f"Kick API'ye bağlanılamadı ({type(exc).__name__}).") from exc

        result: CheckResult = {}
        for slug, ref in by_slug.items():
            channel = found.get(slug)
            if channel is None:
                result[ref.streamer_id] = PlatformError("Kick'te bu kanal bulunamadı.")
                continue
            stream = channel.get("stream") or {}
            is_live = bool(stream.get("is_live"))
            result[ref.streamer_id] = LiveStatus(
                is_live=is_live,
                title=channel.get("stream_title") if is_live else None,
                viewer_count=stream.get("viewer_count") if is_live else None,
                started_at=parse_datetime(stream.get("start_time")) if is_live else None,
                stream_url=ref.channel_url if is_live else None,
                resolved_channel_id=str(channel["broadcaster_user_id"]) if channel.get("broadcaster_user_id") else None,
            )
        return result
