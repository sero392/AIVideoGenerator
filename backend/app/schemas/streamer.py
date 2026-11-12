"""Streamer I/O schemas — ready for the Streamer Management phase (validation rules live here)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.models.enums import StreamPlatform


class StreamerBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    platform: StreamPlatform
    channel_url: HttpUrl
    is_active: bool = True
    recording_permission_confirmed: bool = False
    permission_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("channel_url")
    @classmethod
    def _https_only(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("channel_url must use https")
        return value


class StreamerCreate(StreamerBase):
    pass


class StreamerRead(StreamerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_url: str  # type: ignore[assignment]
    created_at: datetime
