from __future__ import annotations

from fastapi import APIRouter

from app.api.dependencies.common import AppSettings, DbSession
from app.schemas.dashboard import DashboardSummary
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary, summary="Overview page data")
async def dashboard_summary(db: DbSession, settings: AppSettings) -> DashboardSummary:
    return await dashboard_service.get_summary(db, settings)
