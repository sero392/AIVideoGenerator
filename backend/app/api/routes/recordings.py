from __future__ import annotations

import mimetypes
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from app.api.dependencies.common import AppSettings, DbSession
from app.core.exceptions import AppError
from app.models.enums import RecordingSource, RecordingStatus
from app.schemas.recording import (
    InboxError,
    InboxScanResponse,
    LiveRecordingStart,
    RecordingList,
    RecordingRead,
    RecordingSystemInfo,
)
from app.services.recorder import importer, storage
from app.services.recorder import recording_query as query
from app.services.recorder.manager import RecordingManager, get_recording_manager

router = APIRouter(prefix="/recordings", tags=["recordings"])

ManagerDep = Annotated[RecordingManager, Depends(get_recording_manager)]
CHUNK = 4 * 1024 * 1024


class UploadTooLargeError(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    code = "upload_too_large"


@router.get("", response_model=RecordingList, summary="Kayıtları listele")
def list_recordings(
    db: DbSession,
    settings: AppSettings,
    streamer_id: int | None = None,
    status_: Annotated[RecordingStatus | None, Query(alias="status")] = None,
    source: RecordingSource | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RecordingList:
    return query.list_recordings(db, settings, streamer_id=streamer_id, status=status_, source=source, limit=limit, offset=offset)


@router.get("/system", response_model=RecordingSystemInfo, summary="Kayıt araçları ve disk durumu")
def recording_system(db: DbSession, settings: AppSettings, manager: ManagerDep) -> RecordingSystemInfo:
    return query.system_info(db, settings, manager)


@router.post("/live", response_model=RecordingRead, status_code=status.HTTP_201_CREATED, summary="Canlı kaydı başlat")
async def start_live(payload: LiveRecordingStart, db: DbSession, settings: AppSettings, manager: ManagerDep) -> RecordingRead:
    session_id = await manager.start_live(payload.streamer_id)
    return query.get_recording(db, settings, session_id)


@router.post("/import", response_model=RecordingRead, status_code=status.HTTP_201_CREATED, summary="Video dosyası yükle")
async def import_upload(
    db: DbSession,
    settings: AppSettings,
    streamer_id: Annotated[int, Form()],
    file: Annotated[UploadFile, File(description="Yayıncının verdiği kayıt (mp4, mkv, mov, webm, ts, flv, m4v)")],
    title: Annotated[str | None, Form(max_length=300)] = None,
) -> RecordingRead:
    ext = importer.check_extension(file.filename or "")
    limit = int(settings.recording_max_upload_gb * 1024**3)
    target = storage.incoming_dir(settings) / f"{uuid.uuid4().hex}{ext}"
    written = 0
    try:
        with target.open("wb") as out:
            while chunk := await file.read(CHUNK):
                written += len(chunk)
                if written > limit:
                    raise UploadTooLargeError(f"Dosya en fazla {settings.recording_max_upload_gb:g} GB olabilir.")
                out.write(chunk)
        session = await run_in_threadpool(
            importer.import_file,
            db,
            settings,
            streamer_id=streamer_id,
            source=target,
            original_name=file.filename or target.name,
            title=(title or "").strip() or None,
        )
    finally:
        target.unlink(missing_ok=True)
    return query.get_recording(db, settings, session.id)


@router.post("/inbox/scan", response_model=InboxScanResponse, summary="Gelen kutusu klasörünü içe aktar")
def scan_inbox(db: DbSession, settings: AppSettings, manager: ManagerDep) -> InboxScanResponse:
    result = importer.scan_inbox(db, settings)
    return InboxScanResponse(
        imported=[query.get_recording(db, settings, i) for i in result.imported],
        errors=[InboxError(**e) for e in result.errors],
        inbox_path=query.system_info(db, settings, manager).inbox_path,
    )


@router.get("/{recording_id}", response_model=RecordingRead, summary="Kayıt detayı")
def get_recording(recording_id: int, db: DbSession, settings: AppSettings) -> RecordingRead:
    return query.get_recording(db, settings, recording_id)


@router.get("/{recording_id}/file", summary="Kayıt dosyası (izleme / indirme)", response_class=FileResponse)
def recording_file(recording_id: int, db: DbSession, settings: AppSettings) -> FileResponse:
    path = query.file_for_download(db, settings, recording_id)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name, content_disposition_type="inline")


@router.post("/{recording_id}/stop", response_model=RecordingRead, summary="Canlı kaydı durdur")
async def stop_recording(recording_id: int, db: DbSession, settings: AppSettings, manager: ManagerDep) -> RecordingRead:
    await manager.stop(recording_id)
    db.expire_all()
    return query.get_recording(db, settings, recording_id)


@router.delete("/{recording_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Kaydı ve dosyasını sil")
def delete_recording(recording_id: int, db: DbSession, settings: AppSettings) -> Response:
    query.delete_recording(db, settings, recording_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
