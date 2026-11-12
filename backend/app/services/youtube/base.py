"""YouTube publisher interface (implementation: phases 9-10).

OAuth client ID/secret come from ``.env``; the refresh token is stored at
``settings.youtube_token_path`` (outside git). Secrets are never logged.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class UploadRequest:
    file_path: Path
    title: str
    description: str
    tags: list[str]
    privacy_status: str = "private"
    publish_at: datetime | None = None


class YouTubePublisher(ABC):
    @abstractmethod
    def is_authorized(self) -> bool: ...

    @abstractmethod
    async def upload(self, request: UploadRequest) -> str:
        """Upload and return the YouTube video id."""
