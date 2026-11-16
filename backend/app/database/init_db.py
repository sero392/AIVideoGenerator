"""Database bootstrap: runs Alembic migrations on startup.

* Fresh database            -> ``upgrade head`` creates everything.
* v0.1.0 database (created  -> stamped as the baseline revision first, then
  by ``create_all``, no        upgraded, so existing data is kept.
  ``alembic_version`` table)

SQLite foreign keys are switched OFF while migrating. Alembic's batch mode
changes a table by creating a copy and DROPPING the original; with foreign keys
ON, that drop cascades and silently deletes every child row (schedules, statuses,
events, recordings...). This is the procedure SQLite documents for schema changes.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, inspect, text

import app.models  # noqa: F401  (registers all models on Base.metadata)
from app.core.config import BACKEND_DIR

logger = logging.getLogger(__name__)

BASELINE_REVISION = "0001"


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return cfg


@contextmanager
def sqlite_foreign_keys_off(conn: Connection) -> Iterator[None]:
    """Disable FK enforcement for the duration of a migration (no-op on other databases).

    The PRAGMA only takes effect outside a transaction, so it is issued and
    committed before any migration work starts, and verified.
    """
    if conn.dialect.name != "sqlite":
        yield
        return
    conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    conn.commit()
    if conn.exec_driver_sql("PRAGMA foreign_keys").scalar() != 0:
        raise RuntimeError("Could not disable SQLite foreign keys; refusing to migrate (would cascade-delete data).")
    try:
        yield
    finally:
        conn.rollback()  # end any open transaction so the PRAGMA below is honoured
        violations = conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        if violations:
            logger.error("Foreign key violations after migration: %s", violations[:10])
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        conn.commit()


def migrate(engine: Engine, revision: str = "head", *, downgrade: bool = False) -> str | None:
    """Run Alembic to ``revision`` with SQLite foreign keys safely disabled. Returns the new revision."""
    cfg = alembic_config()
    with engine.connect() as conn, sqlite_foreign_keys_off(conn):
        cfg.attributes["connection"] = conn
        tables = set(inspect(conn).get_table_names())
        if "streamers" in tables and "alembic_version" not in tables:
            logger.info("Pre-migration database detected; stamping baseline revision %s.", BASELINE_REVISION)
            command.stamp(cfg, BASELINE_REVISION)
        (command.downgrade if downgrade else command.upgrade)(cfg, revision)
        conn.commit()
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()


def init_db(engine: Engine) -> None:
    revision = migrate(engine)
    logger.info("Database ready (schema revision %s).", revision)


def check_db_connection(engine: Engine) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Database connectivity check failed.")
        return False
