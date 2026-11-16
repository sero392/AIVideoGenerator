"""Migrations must reproduce the models exactly and upgrade pre-Alembic databases."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app.database.base import Base
from app.database.init_db import BASELINE_REVISION, alembic_config, init_db, migrate


def _engine(path: Path):  # type: ignore[no-untyped-def]
    return create_engine(f"sqlite:///{path}")


def test_fresh_database_matches_models(tmp_path: Path) -> None:
    engine = _engine(tmp_path / "fresh.db")
    init_db(engine)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"Models and migrations differ; run 'alembic revision --autogenerate': {diff}"


def test_pre_alembic_database_is_stamped_and_upgraded(tmp_path: Path) -> None:
    engine = _engine(tmp_path / "legacy.db")
    # Simulate a v0.1.0 database: baseline schema + data, but no alembic_version table.
    cfg = alembic_config()
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, BASELINE_REVISION)
        conn.execute(text("DROP TABLE alembic_version"))
        conn.execute(
            text(
                "INSERT INTO streamers (name, platform, channel_url, is_active, recording_permission_confirmed, created_at)"
                " VALUES ('Old', 'twitch', 'https://twitch.tv/old', 1, 0, CURRENT_TIMESTAMP)"
            )
        )

    init_db(engine)

    columns = {c["name"] for c in inspect(engine).get_columns("streamers")}
    assert {"permission_confirmed_at", "updated_at"} <= columns
    with engine.connect() as conn:
        assert conn.execute(text("SELECT name FROM streamers")).scalar() == "Old"
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() != BASELINE_REVISION


def test_downgrade_and_upgrade_keep_child_rows(tmp_path: Path) -> None:
    """Regression: batch-mode table rebuilds must not cascade-delete related rows.

    With SQLite foreign keys ON, rebuilding ``streamers`` (drop + copy) deleted
    every tracking window, status and event of every streamer.
    """
    from sqlalchemy import event

    engine = _engine(tmp_path / "children.db")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):  # type: ignore[no-untyped-def]  (same as the app's engine)
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    init_db(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO streamers (id, name, platform, channel_url, is_active, recording_permission_confirmed,"
            " live_capture_enabled, created_at) VALUES (1, 'S', 'twitch', 'https://twitch.tv/s', 1, 1, 0, CURRENT_TIMESTAMP)"
        ))
        conn.execute(text(
            "INSERT INTO tracking_windows (streamer_id, day_of_week, start_time, end_time, created_at)"
            " VALUES (1, 0, '12:00', '18:00', CURRENT_TIMESTAMP)"
        ))
        conn.execute(text("INSERT INTO stream_events (streamer_id, event_type, occurred_at) VALUES (1, 'went_live', CURRENT_TIMESTAMP)"))

    # 0004 -> 0003 drops streamers.live_capture_enabled: SQLite rebuilds the table (copy + DROP)
    assert migrate(engine, "0003", downgrade=True) == "0003"
    assert migrate(engine) not in (None, "0003")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM tracking_windows")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM stream_events")).scalar() == 1
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1  # re-enabled afterwards
