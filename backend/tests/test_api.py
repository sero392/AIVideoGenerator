from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Clip, ClipStatus, RecordingSession, RecordingStatus, StreamPlatform, Streamer


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "application": "Streamer AI Engine", "version": "0.1.0"}


def test_openapi_docs_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    schema = client.get("/api/v1/openapi.json").json()
    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/dashboard/summary" in schema["paths"]


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_cors_allows_frontend_origin(client: TestClient) -> None:
    response = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_dashboard_empty_database_shows_zeros(client: TestClient, db: Session) -> None:
    data = client.get("/api/v1/dashboard/summary").json()
    assert data["stats"] == {"tracked_streamers": 0, "active_streams": 0, "total_recordings": 0, "prepared_clips": 0}
    assert data["recent_activity"] == []
    components = {c["name"]: c["status"] for c in data["system_status"]["components"]}
    assert components["database"] == "ok"
    assert components["ollama"] == "unavailable"
    assert components["scheduler"] == "disabled"
    assert components["youtube"] == "unavailable"


def test_dashboard_counts_real_rows(client: TestClient, db: Session) -> None:
    active = Streamer(name="A", platform=StreamPlatform.TWITCH, channel_url="https://twitch.tv/a")
    inactive = Streamer(name="B", platform=StreamPlatform.KICK, channel_url="https://kick.com/b", is_active=False)
    db.add_all([active, inactive])
    db.flush()
    live = RecordingSession(streamer_id=active.id, status=RecordingStatus.RECORDING)
    done = RecordingSession(streamer_id=active.id, status=RecordingStatus.COMPLETED)
    db.add_all([live, done])
    db.flush()
    db.add_all(
        [
            Clip(streamer_id=active.id, recording_id=done.id, title="c1", start_time=0, end_time=30, status=ClipStatus.READY),
            Clip(streamer_id=active.id, recording_id=done.id, title="c2", start_time=40, end_time=70, status=ClipStatus.PENDING),
        ]
    )
    db.commit()

    data = client.get("/api/v1/dashboard/summary").json()
    assert data["stats"] == {"tracked_streamers": 1, "active_streams": 1, "total_recordings": 2, "prepared_clips": 1}
    assert len(data["recent_activity"]) == 4


def test_websocket_events(client: TestClient) -> None:
    with client.websocket_connect("/api/v1/ws/events") as ws:
        assert ws.receive_json() == {"type": "connected"}
        ws.send_text("ping")
        assert ws.receive_json() == {"type": "pong"}
