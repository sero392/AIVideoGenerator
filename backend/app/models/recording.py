from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow
from app.models.enums import RecordingStatus

if TYPE_CHECKING:
    from app.models.clip import Clip
    from app.models.streamer import Streamer


class RecordingSession(Base):
    __tablename__ = "recording_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    streamer_id: Mapped[int] = mapped_column(ForeignKey("streamers.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    # Relative to storage/recordings — never an absolute path.
    file_path: Mapped[str | None] = mapped_column(String(500), default=None)
    status: Mapped[RecordingStatus] = mapped_column(
        Enum(RecordingStatus, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        default=RecordingStatus.SCHEDULED,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    streamer: Mapped[Streamer] = relationship(back_populates="recordings")
    clips: Mapped[list[Clip]] = relationship(back_populates="recording", cascade="all, delete-orphan", passive_deletes=True)
