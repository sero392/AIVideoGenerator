"""Central application configuration.

Values come from environment variables (and ``backend/.env``). Secrets are typed
as ``SecretStr`` so they never appear in ``repr()`` output or logs.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "Streamer AI Engine"
    app_version: str = "0.4.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Paths ---
    database_url: str = ""
    storage_root: Path | None = None
    log_dir: Path | None = None
    config_dir: Path | None = None

    # --- AI ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "qwen2.5:7b"
    whisper_model_size: str = "small"
    whisper_device: str = "auto"
    whisper_compute_type: str = "int8"

    # --- Video ---
    # "ffmpeg" = use PATH if present, otherwise the binary bundled by imageio-ffmpeg.
    ffmpeg_binary: str = "ffmpeg"

    # --- Recording ---
    recording_max_concurrent: int = Field(default=2, ge=1, le=10)
    recording_max_hours: float = Field(default=12, gt=0, le=48)
    recording_min_free_gb: float = Field(default=5, ge=0)
    recording_max_upload_gb: float = Field(default=20, gt=0)
    # yt-dlp format sort; "res:1080" = best quality up to 1080p (smaller side, so vertical streams work too)
    recording_format_sort: str = "res:1080"

    # --- Scheduler ---
    scheduler_enabled: bool = True
    scheduler_timezone: str = "Europe/Istanbul"

    # --- Live stream tracking (official platform APIs) ---
    tracking_enabled: bool = True
    tracking_tick_seconds: int = Field(default=60, ge=15, le=3600)
    twitch_poll_interval_seconds: int = Field(default=120, ge=30)
    kick_poll_interval_seconds: int = Field(default=120, ge=30)
    youtube_poll_interval_seconds: int = Field(default=300, ge=60)
    # Twitch Helix app credentials (dev.twitch.tv/console)
    twitch_client_id: str = ""
    twitch_client_secret: SecretStr = Field(default=SecretStr(""))
    # Kick public API app credentials (kick.com/settings/developer)
    kick_client_id: str = ""
    kick_client_secret: SecretStr = Field(default=SecretStr(""))
    # YouTube Data API v3 key (read-only public data; separate from upload OAuth below)
    youtube_api_key: SecretStr = Field(default=SecretStr(""))

    # --- YouTube OAuth (secrets) ---
    youtube_client_id: str = ""
    youtube_client_secret: SecretStr = Field(default=SecretStr(""))
    youtube_redirect_uri: str = "http://localhost:8000/api/v1/youtube/oauth/callback"
    youtube_token_file: Path | None = None

    @field_validator("storage_root", "log_dir", "config_dir", "youtube_token_file", mode="before")
    @classmethod
    def _empty_path_is_none(cls, value: Any) -> Any:
        return None if value in ("", None) else value

    # --- Derived values -------------------------------------------------
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def storage_dir(self) -> Path:
        return (self.storage_root or PROJECT_ROOT / "storage").resolve()

    @property
    def logs_dir(self) -> Path:
        return (self.log_dir or PROJECT_ROOT / "logs").resolve()

    @property
    def config_path(self) -> Path:
        return (self.config_dir or PROJECT_ROOT / "config").resolve()

    @property
    def youtube_token_path(self) -> Path:
        return (self.youtube_token_file or self.storage_dir / "secrets" / "youtube_token.json").resolve()

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_file = self.storage_dir / "database" / "streamer_ai_engine.db"
        return f"sqlite:///{db_file}"

    @property
    def youtube_oauth_configured(self) -> bool:
        return bool(self.youtube_client_id and self.youtube_client_secret.get_secret_value())

    def load_json_config(self, name: str) -> dict[str, Any]:
        """Load a JSON file from the config directory (e.g. ``settings.json``)."""
        path = self.config_path / name
        if not path.is_file():
            return {}
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)


@lru_cache
def get_settings() -> Settings:
    return Settings()
