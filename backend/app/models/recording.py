from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow
from app.models.enums import RecordingSource, RecordingStatus

if TYPE_CHECKING:
    from app.models.clip import Clip
    from app.models.streamer import Streamer


def _enum(cls):  # type: ignore[no-untyped-def]
    return Enum(cls, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e])


class RecordingSession(Base):
    __tablename__ = "recording_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    streamer_id: Mapped[int] = mapped_column(ForeignKey("streamers.id", ondelete="CASCADE"), index=True)
    source: Mapped[RecordingSource] = mapped_column(
        _enum(RecordingSource), default=RecordingSource.LIVE_CAPTURE, server_default=RecordingSource.LIVE_CAPTURE.value
    )
    title: Mapped[str | None] = mapped_column(String(300), default=None)
    # Live: watch URL of the stream. Import: original file name.
    source_url: Mapped[str | None] = mapped_column(String(500), default=None)
    platform_stream_id: Mapped[str | None] = mapped_column(String(100), default=None, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Relative to storage/recordings — never an absolute path.
    file_path: Mapped[str | None] = mapped_column(String(500), default=None)
    duration_seconds: Mapped[float | None] = mapped_column(Float, default=None)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, default=None)
    status: Mapped[RecordingStatus] = mapped_column(_enum(RecordingStatus), default=RecordingStatus.SCHEDULED, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    # Why a live capture ended: manual | stream_ended | max_duration | shutdown | error.
    # "manual" prevents the tracker from auto-restarting the same stream.
    stop_reason: Mapped[str | None] = mapped_column(String(20), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    streamer: Mapped[Streamer] = relationship(back_populates="recordings")
    clips: Mapped[list[Clip]] = relationship(back_populates="recording", cascade="all, delete-orphan", passive_deletes=True)
