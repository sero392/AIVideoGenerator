from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies.common import AppSettings, DbSession
from app.models.enums import StreamPlatform
from app.schemas.streamer import StreamerCreate, StreamerImportResult, StreamerList, StreamerRead, StreamerUpdate
from app.services.streamer import streamer_service as service

router = APIRouter(prefix="/streamers", tags=["streamers"])


@router.get("", response_model=StreamerList, summary="Yayıncıları listele")
def list_streamers(
    db: DbSession,
    search: Annotated[str | None, Query(max_length=100, description="Ad veya kanal adresinde arar")] = None,
    platform: StreamPlatform | None = None,
    is_active: bool | None = None,
    permission_confirmed: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> StreamerList:
    return service.list_streamers(
        db,
        search=search,
        platform=platform,
        is_active=is_active,
        permission_confirmed=permission_confirmed,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=StreamerRead, status_code=status.HTTP_201_CREATED, summary="Yayıncı ekle")
def create_streamer(db: DbSession, payload: StreamerCreate) -> StreamerRead:
    return service.create_streamer(db, payload)


@router.post("/import", response_model=StreamerImportResult, summary="config/streamers.json dosyasından içe aktar")
def import_streamers(db: DbSession, settings: AppSettings) -> StreamerImportResult:
    return service.import_from_config(db, settings)


@router.get("/{streamer_id}", response_model=StreamerRead, summary="Yayıncı detayı")
def get_streamer(db: DbSession, streamer_id: int) -> StreamerRead:
    return service.get_streamer(db, streamer_id)


@router.patch("/{streamer_id}", response_model=StreamerRead, summary="Yayıncıyı güncelle")
def update_streamer(db: DbSession, streamer_id: int, payload: StreamerUpdate) -> StreamerRead:
    return service.update_streamer(db, streamer_id, payload)


@router.delete("/{streamer_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Yayıncıyı sil")
def delete_streamer(db: DbSession, streamer_id: int) -> Response:
    service.delete_streamer(db, streamer_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
