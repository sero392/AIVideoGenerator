from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies.common import AppSettings
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness check")
async def health(settings: AppSettings) -> HealthResponse:
    return HealthResponse(status="ok", application=settings.app_name, version=settings.app_version)
