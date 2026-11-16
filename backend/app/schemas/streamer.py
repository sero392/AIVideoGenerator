"""Streamer I/O schemas.

Field-level rules live here; cross-field business rules (URL must match the
platform, confirmed permission needs notes) live in the streamer service so
they apply equally to create, update and JSON import.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import StreamPlatform


def _strip_required(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Bu alan boş olamaz.")
    return value


class StreamerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    platform: StreamPlatform
    channel_url: str = Field(min_length=1, max_length=500)
    is_active: bool = True
    recording_permission_confirmed: bool = False
    permission_notes: str | None = Field(default=None, max_length=2000)
    live_capture_enabled: bool = False

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return _strip_required(value)


class StreamerUpdate(BaseModel):
    """Partial update: only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    platform: StreamPlatform | None = None
    channel_url: str | None = Field(default=None, min_length=1, max_length=500)
    is_active: bool | None = None
    recording_permission_confirmed: bool | None = None
    permission_notes: str | None = Field(default=None, max_length=2000)
    live_capture_enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        return None if value is None else _strip_required(value)


class StreamerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    platform: StreamPlatform
    channel_url: str
    is_active: bool
    recording_permission_confirmed: bool
    permission_notes: str | None
    permission_confirmed_at: datetime | None
    live_capture_enabled: bool
    created_at: datetime
    updated_at: datetime | None
    recordings_count: int = 0
    clips_count: int = 0


class StreamerList(BaseModel):
    items: list[StreamerRead]
    total: int
    limit: int
    offset: int


class ImportSkipped(BaseModel):
    channel_url: str
    reason: str


class ImportError_(BaseModel):
    index: int
    message: str


class StreamerImportResult(BaseModel):
    created: list[StreamerRead]
    skipped: list[ImportSkipped]
    errors: list[ImportError_]
