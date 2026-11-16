from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow
from app.models.enums import StreamPlatform

if TYPE_CHECKING:
    from app.models.clip import Clip
    from app.models.recording import RecordingSession
    from app.models.tracking import StreamEvent, StreamStatus, TrackingWindow


class Streamer(Base):
    __tablename__ = "streamers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    platform: Mapped[StreamPlatform] = mapped_column(
        Enum(StreamPlatform, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e])
    )
    channel_url: Mapped[str] = mapped_column(String(500), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    # Recording is only allowed once the operator confirms the streamer granted permission.
    recording_permission_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Who granted permission, how and where it is documented (required when confirmed).
    permission_notes: Mapped[str | None] = mapped_column(Text, default=None)
    # Set when permission flips to confirmed, cleared when it is revoked (audit trail).
    permission_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Automatic live capture is opt-in per streamer (requires confirmed permission).
    live_capture_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    # Platform-side channel id resolved by the tracker (e.g. YouTube "UC..."); cleared when the URL changes.
    platform_channel_id: Mapped[str | None] = mapped_column(String(100), default=None)

    recordings: Mapped[list[RecordingSession]] = relationship(
        back_populates="streamer", cascade="all, delete-orphan", passive_deletes=True
    )
    clips: Mapped[list[Clip]] = relationship(back_populates="streamer", cascade="all, delete-orphan", passive_deletes=True)
    tracking_windows: Mapped[list[TrackingWindow]] = relationship(
        back_populates="streamer",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="(TrackingWindow.day_of_week, TrackingWindow.start_time)",
    )
    stream_status: Mapped[StreamStatus | None] = relationship(
        back_populates="streamer", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )
    stream_events: Mapped[list[StreamEvent]] = relationship(
        back_populates="streamer", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<Streamer id={self.id} name={self.name!r} platform={self.platform}>"
