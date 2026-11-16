"""Twitch Helix adapter (app access token, GET /helix/streams).

Docs: https://dev.twitch.tv/docs/api/reference/#get-streams
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

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
STREAMS_URL = "https://api.twitch.tv/helix/streams"
MAX_LOGINS_PER_REQUEST = 100


class TwitchAdapter(PlatformAdapter):
    platform = StreamPlatform.TWITCH
    required_settings = ("TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET")

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
        raise_for_platform(response, "Twitch")
        data = response.json()
        self._token.set(data["access_token"], float(data.get("expires_in", 3600)))
        return data["access_token"]

    async def check(self, channels: list[ChannelRef]) -> CheckResult:
        by_login = {c.path.lower(): c for c in channels}
        live: dict[str, dict] = {}
        try:
            async with self.client() as client:
                token = await self._access_token(client)
                for batch in chunks(list(by_login), MAX_LOGINS_PER_REQUEST):
                    response = await client.get(
                        STREAMS_URL,
                        params=[("user_login", login) for login in batch] + [("first", str(MAX_LOGINS_PER_REQUEST))],
                        headers={"Client-Id": self._client_id, "Authorization": f"Bearer {token}"},
                    )
                    if response.status_code == 401:
                        self._token.clear()  # expired/revoked; fetch a new one next cycle
                    raise_for_platform(response, "Twitch")
                    for stream in response.json().get("data", []):
                        if stream.get("type") == "live":
                            live[str(stream.get("user_login", "")).lower()] = stream
        except httpx.HTTPError as exc:
            raise PlatformError(f"Twitch API'ye bağlanılamadı ({type(exc).__name__}).") from exc

        result: CheckResult = {}
        for login, ref in by_login.items():
            stream = live.get(login)
            result[ref.streamer_id] = (
                LiveStatus(
                    is_live=True,
                    title=stream.get("title"),
                    viewer_count=stream.get("viewer_count"),
                    started_at=parse_datetime(stream.get("started_at")),
                    stream_id=str(stream.get("id")) if stream.get("id") else None,
                    stream_url=ref.channel_url,
                    resolved_channel_id=stream.get("user_id"),
                )
                if stream
                else LiveStatus(is_live=False)
            )
        return result
