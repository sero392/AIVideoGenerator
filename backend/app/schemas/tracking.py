from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import StreamEventType, StreamPlatform, TrackingState
from app.services.streamer.schedule import parse_hhmm

MAX_WINDOWS = 28


class TrackingWindowIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_of_week: int = Field(ge=0, le=6, description="0 = Pazartesi ... 6 = Pazar")
    start_time: str = Field(examples=["20:00"])
    end_time: str = Field(examples=["02:00"], description="Başlangıçtan küçük/eşitse gece yarısını geçer; eşitse 24 saat")

    @field_validator("start_time", "end_time")
    @classmethod
    def _hhmm(cls, value: str) -> str:
        parse_hhmm(value)
        return value


class TrackingWindowRead(TrackingWindowIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    windows: list[TrackingWindowIn] = Field(max_length=MAX_WINDOWS)


class ScheduleRead(BaseModel):
    streamer_id: int
    timezone: str
    windows: list[TrackingWindowRead]


class StreamStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    state: TrackingState
    title: str | None = None
    viewer_count: int | None = None
    live_started_at: datetime | None = None
    stream_url: str | None = None
    error_message: str | None = None
    checked_at: datetime | None = None
    state_changed_at: datetime | None = None


class TrackedStreamer(BaseModel):
    id: int
    name: str
    platform: StreamPlatform
    channel_url: str
    is_active: bool
    recording_permission_confirmed: bool
    live_capture_enabled: bool
    active_recording_id: int | None
    windows: list[TrackingWindowRead]
    status: StreamStatusRead
    in_schedule: bool
    #: End of the current window when in schedule, otherwise the next window start.
    next_change_at: datetime | None


class PlatformInfo(BaseModel):
    platform: StreamPlatform
    configured: bool
    required_settings: list[str]
    poll_interval_seconds: int


class TrackingOverview(BaseModel):
    timezone: str
    tracking_enabled: bool
    tick_seconds: int
    next_cycle_at: datetime | None
    live_count: int
    platforms: list[PlatformInfo]
    streamers: list[TrackedStreamer]


class StreamEventRead(BaseModel):
    id: int
    streamer_id: int
    streamer_name: str
    platform: StreamPlatform
    event_type: StreamEventType
    title: str | None
    occurred_at: datetime
