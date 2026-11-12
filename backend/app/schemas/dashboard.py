from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import ComponentState


class DashboardStats(BaseModel):
    tracked_streamers: int
    active_streams: int
    total_recordings: int
    prepared_clips: int


class ActivityItem(BaseModel):
    kind: Literal["recording", "clip", "youtube"]
    title: str
    status: str
    timestamp: datetime


class ComponentStatus(BaseModel):
    name: str
    status: ComponentState
    detail: str | None = None


class SystemStatus(BaseModel):
    overall: Literal["ok", "degraded", "error"]
    components: list[ComponentStatus]


class DashboardSummary(BaseModel):
    stats: DashboardStats
    recent_activity: list[ActivityItem]
    system_status: SystemStatus
    generated_at: datetime
