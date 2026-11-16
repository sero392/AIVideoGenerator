from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies.common import AppSettings, DbSession
from app.core.exceptions import NotFoundError
from app.models import Streamer
from app.schemas.tracking import ScheduleRead, ScheduleUpdate, StreamEventRead, TrackedStreamer, TrackingOverview
from app.services.recorder.manager import RecordingManager, get_recording_manager
from app.services.streamer import tracking_query as query
from app.services.streamer.tracking_service import Tracker, get_tracker

router = APIRouter(tags=["tracking"])

TrackerDep = Annotated[Tracker, Depends(get_tracker)]
ManagerDep = Annotated[RecordingManager, Depends(get_recording_manager)]


@router.get("/tracking/overview", response_model=TrackingOverview, summary="Takip durumu (tüm yayıncılar)")
def tracking_overview(db: DbSession, tracker: TrackerDep) -> TrackingOverview:
    return query.build_overview(db, tracker)


@router.get("/tracking/events", response_model=list[StreamEventRead], summary="Son canlı/çevrimdışı geçişleri")
def tracking_events(db: DbSession, limit: Annotated[int, Query(ge=1, le=100)] = 20) -> list[StreamEventRead]:
    return query.list_events(db, limit)


@router.post(
    "/tracking/streamers/{streamer_id}/check",
    response_model=TrackedStreamer,
    summary="Şimdi kontrol et (takvim ve aralık beklenmeden)",
)
async def check_now(streamer_id: int, db: DbSession, tracker: TrackerDep, recorder: ManagerDep) -> TrackedStreamer:
    if db.get(Streamer, streamer_id) is None:
        raise NotFoundError("Yayıncı bulunamadı.", details={"id": streamer_id})
    await tracker.run_cycle(force_ids={streamer_id})
    await recorder.sync_with_tracking()
    db.expire_all()
    return next(s for s in query.build_overview(db, tracker).streamers if s.id == streamer_id)


@router.get("/streamers/{streamer_id}/schedule", response_model=ScheduleRead, summary="Haftalık takip takvimi")
def get_schedule(streamer_id: int, db: DbSession, settings: AppSettings) -> ScheduleRead:
    return query.get_schedule(db, streamer_id, settings.scheduler_timezone)


@router.put("/streamers/{streamer_id}/schedule", response_model=ScheduleRead, summary="Haftalık takvimi değiştir")
def put_schedule(streamer_id: int, payload: ScheduleUpdate, db: DbSession, settings: AppSettings) -> ScheduleRead:
    return query.replace_schedule(db, streamer_id, payload, settings.scheduler_timezone)
