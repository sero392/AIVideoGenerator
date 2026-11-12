from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, utcnow


class AIModel(Base):
    """A configured AI model (e.g. Ollama ``qwen2.5:7b`` or faster-whisper ``small``)."""

    __tablename__ = "ai_models"
    __table_args__ = (UniqueConstraint("provider", "model_identifier", name="provider_model"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(50), index=True)
    model_identifier: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    # Provider-specific options (temperature, context size, device...). Never store secrets here.
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
