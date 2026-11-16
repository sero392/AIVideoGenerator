"""Streamer management: CRUD, business rules and JSON import."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.database.base import utcnow
from app.models import Clip, RecordingSession, Streamer
from app.models.enums import StreamPlatform
from app.schemas.streamer import (
    ImportError_,
    ImportSkipped,
    StreamerCreate,
    StreamerImportResult,
    StreamerList,
    StreamerRead,
    StreamerUpdate,
)
from app.services.streamer.channel_url import normalize_channel_url

logger = logging.getLogger(__name__)

IMPORT_FILE = "streamers.json"


# --- helpers -----------------------------------------------------------------
def _counts_query():  # type: ignore[no-untyped-def]
    recordings = (
        select(func.count(RecordingSession.id)).where(RecordingSession.streamer_id == Streamer.id).scalar_subquery()
    )
    clips = select(func.count(Clip.id)).where(Clip.streamer_id == Streamer.id).scalar_subquery()
    return select(Streamer, recordings.label("recordings_count"), clips.label("clips_count"))


def _to_read(streamer: Streamer, recordings_count: int = 0, clips_count: int = 0) -> StreamerRead:
    data = StreamerRead.model_validate(streamer)
    data.recordings_count = recordings_count
    data.clips_count = clips_count
    return data


def _normalized_url(platform: StreamPlatform, url: str) -> str:
    try:
        return normalize_channel_url(platform, url)
    except ValueError as exc:
        raise DomainValidationError("channel_url", str(exc)) from exc


def _clean_notes(notes: str | None) -> str | None:
    notes = (notes or "").strip()
    return notes or None


def _check_permission_rule(confirmed: bool, notes: str | None) -> None:
    if confirmed and not notes:
        raise DomainValidationError(
            "permission_notes",
            "Kayıt izni onaylanırken iznin kimden, nasıl ve ne zaman alındığını not olarak girmelisiniz.",
        )


def _check_capture_rule(capture: bool, confirmed: bool) -> None:
    if capture and not confirmed:
        raise DomainValidationError(
            "live_capture_enabled", "Canlı kayıt yalnızca kayıt izni onaylanmış yayıncılar için açılabilir."
        )


def _ensure_unique_url(db: Session, url: str, *, exclude_id: int | None = None) -> None:
    stmt = select(Streamer.id).where(Streamer.channel_url == url)
    if exclude_id is not None:
        stmt = stmt.where(Streamer.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise ConflictError("Bu kanal adresiyle kayıtlı bir yayıncı zaten var.", details={"channel_url": url})


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:  # race on the unique constraint
        db.rollback()
        raise ConflictError("Bu kanal adresiyle kayıtlı bir yayıncı zaten var.") from exc


def _get(db: Session, streamer_id: int) -> Streamer:
    streamer = db.get(Streamer, streamer_id)
    if streamer is None:
        raise NotFoundError("Yayıncı bulunamadı.", details={"id": streamer_id})
    return streamer


# --- queries -----------------------------------------------------------------
def list_streamers(
    db: Session,
    *,
    search: str | None = None,
    platform: StreamPlatform | None = None,
    is_active: bool | None = None,
    permission_confirmed: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> StreamerList:
    filters: list[Any] = []
    if search and search.strip():
        # Escape LIKE wildcards so user input is matched literally.
        term = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{term}%"
        filters.append(or_(Streamer.name.ilike(pattern, escape="\\"), Streamer.channel_url.ilike(pattern, escape="\\")))
    if platform is not None:
        filters.append(Streamer.platform == platform)
    if is_active is not None:
        filters.append(Streamer.is_active.is_(is_active))
    if permission_confirmed is not None:
        filters.append(Streamer.recording_permission_confirmed.is_(permission_confirmed))

    total = int(db.scalar(select(func.count(Streamer.id)).where(*filters)) or 0)
    rows = db.execute(
        _counts_query().where(*filters).order_by(Streamer.created_at.desc(), Streamer.id.desc()).limit(limit).offset(offset)
    ).all()
    return StreamerList(items=[_to_read(s, r, c) for s, r, c in rows], total=total, limit=limit, offset=offset)


def get_streamer(db: Session, streamer_id: int) -> StreamerRead:
    row = db.execute(_counts_query().where(Streamer.id == streamer_id)).first()
    if row is None:
        raise NotFoundError("Yayıncı bulunamadı.", details={"id": streamer_id})
    return _to_read(*row)


# --- commands ----------------------------------------------------------------
def create_streamer(db: Session, payload: StreamerCreate) -> StreamerRead:
    url = _normalized_url(payload.platform, payload.channel_url)
    notes = _clean_notes(payload.permission_notes)
    _check_permission_rule(payload.recording_permission_confirmed, notes)
    _check_capture_rule(payload.live_capture_enabled, payload.recording_permission_confirmed)
    _ensure_unique_url(db, url)

    streamer = Streamer(
        name=payload.name,
        platform=payload.platform,
        channel_url=url,
        is_active=payload.is_active,
        recording_permission_confirmed=payload.recording_permission_confirmed,
        permission_notes=notes,
        permission_confirmed_at=utcnow() if payload.recording_permission_confirmed else None,
        live_capture_enabled=payload.live_capture_enabled,
    )
    db.add(streamer)
    _commit(db)
    logger.info("Streamer created: id=%s platform=%s", streamer.id, streamer.platform.value)
    return get_streamer(db, streamer.id)


def update_streamer(db: Session, streamer_id: int, payload: StreamerUpdate) -> StreamerRead:
    streamer = _get(db, streamer_id)
    changes = payload.model_dump(exclude_unset=True)
    for key in ("name", "platform", "is_active", "recording_permission_confirmed", "live_capture_enabled"):
        if changes.get(key) is None:
            changes.pop(key, None)  # explicit null is not allowed for these

    platform = changes.get("platform", streamer.platform)
    if "channel_url" in changes or "platform" in changes:
        raw_url = changes.get("channel_url") or streamer.channel_url
        url = _normalized_url(platform, raw_url)
        _ensure_unique_url(db, url, exclude_id=streamer.id)
        changes["channel_url"] = url
        if url != streamer.channel_url or platform != streamer.platform:
            # Different channel: forget the resolved platform id and the old live status.
            streamer.platform_channel_id = None
            if streamer.stream_status is not None:
                db.delete(streamer.stream_status)

    notes = _clean_notes(changes["permission_notes"]) if "permission_notes" in changes else streamer.permission_notes
    confirmed = changes.get("recording_permission_confirmed", streamer.recording_permission_confirmed)
    _check_permission_rule(confirmed, notes)
    if not confirmed:
        # Revoking permission always switches automatic capture off.
        if changes.get("live_capture_enabled"):
            _check_capture_rule(True, False)
        changes["live_capture_enabled"] = False
    if "permission_notes" in changes:
        changes["permission_notes"] = notes

    if confirmed and not streamer.recording_permission_confirmed:
        streamer.permission_confirmed_at = utcnow()
    elif not confirmed:
        streamer.permission_confirmed_at = None

    for key, value in changes.items():
        setattr(streamer, key, value)
    _commit(db)
    logger.info("Streamer updated: id=%s fields=%s", streamer.id, sorted(changes))
    return get_streamer(db, streamer.id)


def delete_streamer(db: Session, streamer_id: int) -> None:
    streamer = _get(db, streamer_id)
    has_recordings = db.scalar(select(func.count(RecordingSession.id)).where(RecordingSession.streamer_id == streamer.id))
    if has_recordings:
        raise ConflictError(
            "Bu yayıncıya ait kayıtlar var. Kayıtları ve kesitleri korumak için silmek yerine yayıncıyı pasif yapın.",
            details={"recordings_count": has_recordings},
        )
    db.delete(streamer)
    db.commit()
    logger.info("Streamer deleted: id=%s", streamer_id)


def import_from_config(db: Session, settings: Settings) -> StreamerImportResult:
    """Create streamers listed in ``config/streamers.json``; existing channels are skipped."""
    path = settings.config_path / IMPORT_FILE
    if not path.is_file():
        raise NotFoundError(f"config/{IMPORT_FILE} bulunamadı.")
    try:
        entries = settings.load_json_config(IMPORT_FILE).get("streamers", [])
    except ValueError as exc:  # json.JSONDecodeError is a ValueError
        raise DomainValidationError("file", f"config/{IMPORT_FILE} geçerli bir JSON değil: {exc}") from exc
    if not isinstance(entries, list):
        raise DomainValidationError("file", '"streamers" alanı bir liste olmalıdır.')

    result = StreamerImportResult(created=[], skipped=[], errors=[])
    for index, entry in enumerate(entries):
        try:
            payload = StreamerCreate.model_validate(entry)
            result.created.append(create_streamer(db, payload))
        except ConflictError:
            result.skipped.append(ImportSkipped(channel_url=str(entry.get("channel_url", "")), reason="Zaten kayıtlı"))
        except DomainValidationError as exc:
            result.errors.append(ImportError_(index=index, message=exc.message))
        except ValidationError as exc:
            fields = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())
            result.errors.append(ImportError_(index=index, message=f"Geçersiz alanlar: {fields}"))
        except (AttributeError, TypeError):
            result.errors.append(ImportError_(index=index, message="Kayıt bir JSON nesnesi olmalıdır."))
    logger.info(
        "Streamer import: created=%d skipped=%d errors=%d", len(result.created), len(result.skipped), len(result.errors)
    )
    return result
