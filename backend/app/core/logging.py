"""Logging setup: console + rotating file, with secret redaction."""

from __future__ import annotations

import logging
import logging.config
import re
from pathlib import Path

from app.core.config import Settings

# key=value / "key": "value" pairs whose value must never reach a log file.
_SENSITIVE_KEYS = r"(?:client_secret|secret|password|passwd|token|access_token|refresh_token|api_key|apikey|authorization)"
# Order matters: mask "Bearer <token>" before the generic key=value rule,
# otherwise "Authorization: Bearer x" would only mask the word "Bearer".
_REDACT_PATTERNS = [
    re.compile(r"(Bearer\s+)([A-Za-z0-9\-._~+/]+=*)", re.IGNORECASE),
    # API keys passed as URL query parameters (e.g. YouTube Data API "?key=...")
    re.compile(r"([?&](?:key|client_secret|access_token|token)=)([^&\s\"']+)", re.IGNORECASE),
    re.compile(rf"({_SENSITIVE_KEYS}\s*[=:]\s*[\"']?)([^\s\"'&,}}]+)", re.IGNORECASE),
]
REDACTED = "***REDACTED***"


def redact(text: str) -> str:
    for pattern in _REDACT_PATTERNS:
        text = pattern.sub(lambda m: m.group(1) + REDACTED, text)
    return text


class RedactingFilter(logging.Filter):
    """Masks secrets in the fully formatted message."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        cleaned = redact(message)
        if cleaned != message:
            record.msg = cleaned
            record.args = None
        return True


def setup_logging(settings: Settings) -> None:
    log_dir: Path = settings.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {"redact": {"()": RedactingFilter}},
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "filters": ["redact"],
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "default",
                    "filters": ["redact"],
                    "filename": str(log_dir / "backend.log"),
                    "maxBytes": 5 * 1024 * 1024,
                    "backupCount": 5,
                    "encoding": "utf-8",
                },
            },
            "root": {"level": settings.log_level, "handlers": ["console", "file"]},
            "loggers": {
                "uvicorn.access": {"level": "WARNING"},
                "sqlalchemy.engine": {"level": "WARNING"},
                "apscheduler": {"level": "WARNING"},
                # httpx logs full request URLs at INFO; URLs can carry API keys.
                "httpx": {"level": "WARNING"},
                "httpcore": {"level": "WARNING"},
            },
        }
    )
