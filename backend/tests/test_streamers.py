from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import RecordingSession, Streamer

API = "/api/v1/streamers"


def _create(client: TestClient, **overrides) -> dict:  # type: ignore[no-untyped-def]
    body = {"name": "Streamer One", "platform": "twitch", "channel_url": "https://twitch.tv/one"} | overrides
    response = client.post(API, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _error_field(response) -> str:  # type: ignore[no-untyped-def]
    return response.json()["error"]["details"][0]["loc"][-1]


# --- create ------------------------------------------------------------------
def test_create_normalizes_and_defaults(client: TestClient, db: Session) -> None:
    data = _create(client, channel_url="https://www.twitch.tv/One/")
    assert data["channel_url"] == "https://twitch.tv/one"
    assert data["is_active"] is True
    assert data["recording_permission_confirmed"] is False
    assert data["permission_confirmed_at"] is None
    assert data["recordings_count"] == 0


def test_create_duplicate_url_conflicts(client: TestClient, db: Session) -> None:
    _create(client)
    response = client.post(API, json={"name": "Dup", "platform": "twitch", "channel_url": "https://TWITCH.tv/one"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_create_url_must_match_platform(client: TestClient, db: Session) -> None:
    response = client.post(API, json={"name": "X", "platform": "kick", "channel_url": "https://twitch.tv/x"})
    assert response.status_code == 422
    assert _error_field(response) == "channel_url"


def test_confirmed_permission_requires_notes(client: TestClient, db: Session) -> None:
    body = {"name": "X", "platform": "twitch", "channel_url": "https://twitch.tv/x", "recording_permission_confirmed": True}
    response = client.post(API, json=body | {"permission_notes": "   "})
    assert response.status_code == 422
    assert _error_field(response) == "permission_notes"

    data = _create(client, **body, permission_notes="E-posta ile yazılı izin, 2026-11-10")
    assert data["recording_permission_confirmed"] is True
    assert data["permission_confirmed_at"] is not None


@pytest.mark.parametrize(
    "body",
    [
        {"platform": "twitch", "channel_url": "https://twitch.tv/x"},
        {"name": "x" * 101, "platform": "twitch", "channel_url": "https://twitch.tv/x"},
        {"name": "X", "platform": "myspace", "channel_url": "https://twitch.tv/x"},
        {"name": "X", "platform": "twitch", "channel_url": "https://twitch.tv/x", "id": 99},
    ],
)
def test_create_rejects_invalid_body(client: TestClient, db: Session, body: dict) -> None:
    assert client.post(API, json=body).status_code == 422


# --- read / list -------------------------------------------------------------
def test_get_and_404(client: TestClient, db: Session) -> None:
    created = _create(client)
    assert client.get(f"{API}/{created['id']}").json()["name"] == "Streamer One"
    response = client.get(f"{API}/9999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_list_filters_and_pagination(client: TestClient, db: Session) -> None:
    _create(client, name="Alpha", channel_url="https://twitch.tv/alpha")
    _create(client, name="Beta", platform="kick", channel_url="https://kick.com/beta", is_active=False)
    _create(client, name="Gamma_100%", platform="youtube", channel_url="https://youtube.com/@gamma")

    assert client.get(API).json()["total"] == 3
    assert [s["name"] for s in client.get(API, params={"platform": "kick"}).json()["items"]] == ["Beta"]
    assert client.get(API, params={"is_active": "false"}).json()["total"] == 1
    assert client.get(API, params={"search": "alp"}).json()["items"][0]["name"] == "Alpha"
    assert client.get(API, params={"search": "kick.com"}).json()["total"] == 1
    # LIKE wildcards are matched literally
    assert client.get(API, params={"search": "%"}).json()["total"] == 1
    assert client.get(API, params={"search": "_"}).json()["total"] == 1

    page = client.get(API, params={"limit": 2, "offset": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 1
    assert client.get(API, params={"limit": 0}).status_code == 422


def test_list_includes_counts(client: TestClient, db: Session) -> None:
    created = _create(client)
    db.add(RecordingSession(streamer_id=created["id"]))
    db.commit()
    assert client.get(API).json()["items"][0]["recordings_count"] == 1


# --- update ------------------------------------------------------------------
def test_partial_update(client: TestClient, db: Session) -> None:
    created = _create(client)
    response = client.patch(f"{API}/{created['id']}", json={"name": "  Renamed  ", "is_active": False})
    data = response.json()
    assert response.status_code == 200
    assert data["name"] == "Renamed" and data["is_active"] is False
    assert data["channel_url"] == created["channel_url"]


def test_update_permission_lifecycle(client: TestClient, db: Session) -> None:
    created = _create(client)
    url = f"{API}/{created['id']}"

    assert client.patch(url, json={"recording_permission_confirmed": True}).status_code == 422
    granted = client.patch(url, json={"recording_permission_confirmed": True, "permission_notes": "Sözleşme #12"}).json()
    assert granted["permission_confirmed_at"] is not None

    # Clearing the notes while permission is still confirmed is not allowed
    assert client.patch(url, json={"permission_notes": ""}).status_code == 422

    revoked = client.patch(url, json={"recording_permission_confirmed": False}).json()
    assert revoked["recording_permission_confirmed"] is False
    assert revoked["permission_confirmed_at"] is None


def test_update_platform_revalidates_url(client: TestClient, db: Session) -> None:
    created = _create(client)
    response = client.patch(f"{API}/{created['id']}", json={"platform": "kick"})
    assert response.status_code == 422
    ok = client.patch(f"{API}/{created['id']}", json={"platform": "kick", "channel_url": "https://kick.com/one"})
    assert ok.json()["channel_url"] == "https://kick.com/one"


def test_update_url_conflict(client: TestClient, db: Session) -> None:
    _create(client)
    other = _create(client, name="Two", channel_url="https://twitch.tv/two")
    response = client.patch(f"{API}/{other['id']}", json={"channel_url": "https://twitch.tv/one"})
    assert response.status_code == 409


def test_update_404(client: TestClient, db: Session) -> None:
    assert client.patch(f"{API}/9999", json={"name": "x"}).status_code == 404


# --- delete ------------------------------------------------------------------
def test_delete(client: TestClient, db: Session) -> None:
    created = _create(client)
    assert client.delete(f"{API}/{created['id']}").status_code == 204
    assert client.get(f"{API}/{created['id']}").status_code == 404


def test_delete_blocked_when_recordings_exist(client: TestClient, db: Session) -> None:
    created = _create(client)
    db.add(RecordingSession(streamer_id=created["id"]))
    db.commit()
    response = client.delete(f"{API}/{created['id']}")
    assert response.status_code == 409
    assert db.get(Streamer, created["id"]) is not None


# --- import ------------------------------------------------------------------
@pytest.fixture()
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(get_settings(), "config_dir", tmp_path)
    return tmp_path


def test_import_from_config(client: TestClient, db: Session, config_dir: Path) -> None:
    _create(client, channel_url="https://twitch.tv/existing")
    entries = [
        {"name": "New", "platform": "kick", "channel_url": "https://kick.com/new"},
        {"name": "Existing", "platform": "twitch", "channel_url": "https://www.twitch.tv/Existing"},
        {"name": "Bad", "platform": "twitch", "channel_url": "https://kick.com/bad"},
        {"name": "NoNotes", "platform": "twitch", "channel_url": "https://twitch.tv/n", "recording_permission_confirmed": True},
        {"platform": "twitch"},
        "not-an-object",
    ]
    (config_dir / "streamers.json").write_text(json.dumps({"streamers": entries}), encoding="utf-8")

    result = client.post(f"{API}/import").json()
    assert [s["name"] for s in result["created"]] == ["New"]
    assert len(result["skipped"]) == 1
    assert [e["index"] for e in result["errors"]] == [2, 3, 4, 5]
    assert client.get(API).json()["total"] == 2


def test_import_missing_or_invalid_file(client: TestClient, db: Session, config_dir: Path) -> None:
    assert client.post(f"{API}/import").status_code == 404
    (config_dir / "streamers.json").write_text("{not json", encoding="utf-8")
    assert client.post(f"{API}/import").status_code == 422
