from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import RecordingSource, RecordingStatus, StreamPlatform


class RecordingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    streamer_id: int
    streamer_name: str
    platform: StreamPlatform
    source: RecordingSource
    title: str | None
    source_url: str | None
    status: RecordingStatus
    stop_reason: str | None
    started_at: datetime | None
    ended_at: datetime | None
    duration_seconds: float | None
    #: Final size when finished; bytes written so far while recording.
    file_size_bytes: int | None
    file_available: bool
    error_message: str | None
    created_at: datetime


class RecordingList(BaseModel):
    items: list[RecordingRead]
    total: int
    limit: int
    offset: int


class LiveRecordingStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    streamer_id: int


class InboxError(BaseModel):
    file: str
    message: str


class InboxScanResponse(BaseModel):
    imported: list[RecordingRead]
    errors: list[InboxError]
    inbox_path: str


class RecordingSystemInfo(BaseModel):
    ffmpeg_available: bool
    ffmpeg_source: str | None  # "system" | "bundled"
    ytdlp_version: str | None
    js_runtime_available: bool
    free_gb: float
    min_free_gb: float
    max_concurrent: int
    active_count: int
    max_hours: float
    max_upload_gb: float
    inbox_path: str
    allowed_extensions: list[str]
