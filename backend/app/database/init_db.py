"""Database bootstrap.

Phase 1 uses ``metadata.create_all`` for zero-friction setup. When the schema
starts evolving, switch to Alembic: point ``target_metadata`` at
``app.database.base.Base.metadata`` (models are registered via ``app.models``)
and replace this call with ``alembic upgrade head``.
"""

from __future__ import annotations

import logging

from sqlalchemy import Engine, text

import app.models  # noqa: F401  (registers all models on Base.metadata)
from app.database.base import Base

logger = logging.getLogger(__name__)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)
    logger.info("Database ready (%d tables).", len(Base.metadata.tables))


def check_db_connection(engine: Engine) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Database connectivity check failed.")
        return False
