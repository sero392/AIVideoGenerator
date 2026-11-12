"""Test isolation: every test session uses a throwaway SQLite DB, storage and log dir."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="sae-tests-"))
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": f"sqlite:///{_TMP / 'test.db'}",
        "STORAGE_ROOT": str(_TMP / "storage"),
        "LOG_DIR": str(_TMP / "logs"),
        "SCHEDULER_ENABLED": "false",
        # Port 9 (discard) is closed locally -> fast, deterministic "unavailable".
        "OLLAMA_BASE_URL": "http://127.0.0.1:9",
        "YOUTUBE_CLIENT_ID": "",
        "YOUTUBE_CLIENT_SECRET": "",
    }
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database.base import Base  # noqa: E402
from app.database.session import get_engine, get_session_factory  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:  # runs lifespan -> creates tables
        yield c


@pytest.fixture()
def db(client: TestClient) -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
        # Clean every table between tests
        with get_engine().begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())
