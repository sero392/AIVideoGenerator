"""Live tracking: weekly schedule windows, current stream status, transition log."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow
from app.models.enums import StreamEventType, TrackingState

if TYPE_CHECKING:
    from app.models.streamer import Streamer


def _enum(cls):  # type: ignore[no-untyped-def]
    return Enum(cls, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e])


class TrackingWindow(Base):
    """A weekly time range in which a streamer is polled.

    ``start_time``/``end_time`` are "HH:MM" in the scheduler timezone. When
    ``end_time <= start_time`` the window crosses midnight into the next day;
    ``start_time == end_time`` means the full 24 hours.
    """

    __tablename__ = "tracking_windows"
    __table_args__ = (CheckConstraint("day_of_week >= 0 AND day_of_week <= 6", name="day_of_week_range"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    streamer_id: Mapped[int] = mapped_column(ForeignKey("streamers.id", ondelete="CASCADE"), index=True)
    day_of_week: Mapped[int] = mapped_column(Integer)  # 0 = Monday ... 6 = Sunday
    start_time: Mapped[str] = mapped_column(String(5))
    end_time: Mapped[str] = mapped_column(String(5))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    streamer: Mapped[Streamer] = relationship(back_populates="tracking_windows")


class StreamStatus(Base):
    """Latest known live state of a streamer (one row per streamer)."""

    __tablename__ = "stream_statuses"

    streamer_id: Mapped[int] = mapped_column(ForeignKey("streamers.id", ondelete="CASCADE"), primary_key=True)
    state: Mapped[TrackingState] = mapped_column(_enum(TrackingState), default=TrackingState.PENDING, index=True)
    title: Mapped[str | None] = mapped_column(String(300), default=None)
    viewer_count: Mapped[int | None] = mapped_column(Integer, default=None)
    live_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    stream_url: Mapped[str | None] = mapped_column(String(500), default=None)
    platform_stream_id: Mapped[str | None] = mapped_column(String(100), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    state_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    streamer: Mapped[Streamer] = relationship(back_populates="stream_status")


class StreamEvent(Base):
    """Append-only log of live/offline transitions (feeds the activity list and phase 3 recorder)."""

    __tablename__ = "stream_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    streamer_id: Mapped[int] = mapped_column(ForeignKey("streamers.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[StreamEventType] = mapped_column(_enum(StreamEventType))
    title: Mapped[str | None] = mapped_column(String(300), default=None)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    streamer: Mapped[Streamer] = relationship(back_populates="stream_events")
