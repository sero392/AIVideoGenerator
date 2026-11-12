from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow
from app.models.enums import ClipStatus

if TYPE_CHECKING:
    from app.models.recording import RecordingSession
    from app.models.streamer import Streamer
    from app.models.youtube_video import YoutubeVideo


class Clip(Base):
    __tablename__ = "clips"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="valid_time_range"),
        CheckConstraint("ai_score IS NULL OR (ai_score >= 0 AND ai_score <= 1)", name="ai_score_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    streamer_id: Mapped[int] = mapped_column(ForeignKey("streamers.id", ondelete="CASCADE"), index=True)
    recording_id: Mapped[int] = mapped_column(ForeignKey("recording_sessions.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    # Offsets in seconds from the start of the recording.
    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)
    # Relative to storage/clips.
    file_path: Mapped[str | None] = mapped_column(String(500), default=None)
    # Normalised 0..1 "importance" score from the AI pipeline.
    ai_score: Mapped[float | None] = mapped_column(Float, default=None)
    status: Mapped[ClipStatus] = mapped_column(
        Enum(ClipStatus, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        default=ClipStatus.PENDING,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    streamer: Mapped[Streamer] = relationship(back_populates="clips")
    recording: Mapped[RecordingSession] = relationship(back_populates="clips")
    youtube_videos: Mapped[list[YoutubeVideo]] = relationship(
        back_populates="clip", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
