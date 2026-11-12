"""FastAPI application entry point.

Run from ``backend/``::

    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_v1_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.paths import ensure_storage_dirs
from app.database.init_db import init_db
from app.database.session import get_engine
from app.scheduler.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        ensure_storage_dirs(settings)
        init_db(get_engine())
        start_scheduler(settings)
        logger.info("%s v%s started (%s).", settings.app_name, settings.app_version, settings.environment)
        try:
            yield
        finally:
            stop_scheduler()
            logger.info("Shutdown complete.")

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Permission-aware stream recording, AI highlight detection and YouTube publishing.",
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
