from __future__ import annotations

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.session import get_engine
from app.models import (
    AIModel,
    Clip,
    RecordingSession,
    StreamPlatform,
    Streamer,
    SystemSetting,
    YoutubeVideo,
    YoutubeVideoStatus,
)


def test_all_tables_created(client) -> None:  # noqa: ANN001
    tables = set(inspect(get_engine()).get_table_names())
    assert {"streamers", "recording_sessions", "clips", "youtube_videos", "ai_models", "system_settings"} <= tables


def _graph(db: Session) -> tuple[Streamer, RecordingSession, Clip, YoutubeVideo]:
    streamer = Streamer(name="S", platform=StreamPlatform.YOUTUBE, channel_url="https://youtube.com/@s")
    recording = RecordingSession(streamer=streamer, file_path="s/2026-11-12.mp4")
    clip = Clip(streamer=streamer, recording=recording, title="Moment", start_time=10, end_time=40, ai_score=0.8)
    video = YoutubeVideo(clip=clip, title="Moment")
    db.add(streamer)
    db.commit()
    return streamer, recording, clip, video


def test_relationships_and_defaults(db: Session) -> None:
    streamer, recording, clip, video = _graph(db)
    assert streamer.recording_permission_confirmed is False  # opt-in, never implied
    assert recording.clips == [clip]
    assert clip.duration == 30
    assert clip.youtube_videos[0].status == YoutubeVideoStatus.DRAFT
    assert video.clip.recording.streamer.name == "S"


def test_deleting_streamer_cascades(db: Session) -> None:
    streamer, *_ = _graph(db)
    db.delete(streamer)
    db.commit()
    assert db.scalars(select(Clip)).all() == []
    assert db.scalars(select(YoutubeVideo)).all() == []


def test_clip_time_range_constraint(db: Session) -> None:
    streamer, recording, *_ = _graph(db)
    db.add(Clip(streamer=streamer, recording=recording, title="bad", start_time=50, end_time=10))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_ai_model_and_settings(db: Session) -> None:
    db.add(AIModel(name="Qwen 2.5 7B", provider="ollama", model_identifier="qwen2.5:7b", configuration={"temperature": 0.2}))
    db.add(SystemSetting(setting_key="ui.language", setting_value="tr"))
    db.commit()
    model = db.scalars(select(AIModel)).one()
    assert model.configuration == {"temperature": 0.2}
    db.add(SystemSetting(setting_key="ui.language", setting_value="en"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
