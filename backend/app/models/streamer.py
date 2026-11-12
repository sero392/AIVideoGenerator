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
    permission_notes: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    recordings: Mapped[list[RecordingSession]] = relationship(
        back_populates="streamer", cascade="all, delete-orphan", passive_deletes=True
    )
    clips: Mapped[list[Clip]] = relationship(back_populates="streamer", cascade="all, delete-orphan", passive_deletes=True)

    def __repr__(self) -> str:
        return f"<Streamer id={self.id} name={self.name!r} platform={self.platform}>"
