from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow
from app.models.enums import YoutubeVideoStatus

if TYPE_CHECKING:
    from app.models.clip import Clip


class YoutubeVideo(Base):
    __tablename__ = "youtube_videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    clip_id: Mapped[int] = mapped_column(ForeignKey("clips.id", ondelete="CASCADE"), index=True)
    # Assigned by YouTube after upload; null while still a draft.
    youtube_video_id: Mapped[str | None] = mapped_column(String(32), unique=True, default=None)
    title: Mapped[str] = mapped_column(String(100))  # YouTube title limit is 100 chars
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    status: Mapped[YoutubeVideoStatus] = mapped_column(
        Enum(YoutubeVideoStatus, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        default=YoutubeVideoStatus.DRAFT,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    clip: Mapped[Clip] = relationship(back_populates="youtube_videos")
