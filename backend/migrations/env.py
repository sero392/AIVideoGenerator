"""Alembic environment.

Two entry points:
* CLI (``alembic upgrade head``): builds an engine from app settings.
* App startup (``init_db``): passes an open connection via ``config.attributes``.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection

import app.models  # noqa: F401  (registers models on Base.metadata)
from app.database.base import Base
from app.database.session import get_engine

config = context.config
target_metadata = Base.metadata

# Only configure logging for CLI runs; the app has its own logging setup.
if config.config_file_name is not None and "connection" not in config.attributes:
    fileConfig(config.config_file_name)


def _run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite needs batch mode for ALTER-style changes
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=str(get_engine().url),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)  # caller (app.database.init_db) already disabled SQLite FKs
        return
    from app.database.init_db import sqlite_foreign_keys_off

    with get_engine().connect() as conn, sqlite_foreign_keys_off(conn):
        _run(conn)
        conn.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
