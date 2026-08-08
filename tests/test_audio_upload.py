from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.audio_storage import MAX_UPLOAD_SIZE_BYTES, AudioStorage, get_audio_storage

client = TestClient(app)


def create_meeting() -> str:
    response = client.post("/api/v1/meetings", json={"title": "Upload test"})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def audio_storage_root(tmp_path: Path) -> Path:
    storage_root = tmp_path / "audio"
    app.dependency_overrides[get_audio_storage] = lambda: AudioStorage(storage_root)
    yield storage_root
    app.dependency_overrides.pop(get_audio_storage, None)


@pytest.mark.parametrize(
    ("extension", "content_type"),
    [
        (".mp3", "audio/mpeg"),
        (".wav", "audio/wav"),
        (".m4a", "audio/mp4"),
    ],
)
def test_upload_supported_audio_file(
    extension: str,
    content_type: str,
    audio_storage_root: Path,
) -> None:
    meeting_id = create_meeting()
    content = b"sample audio content"

    response = client.post(
        f"/api/v1/meetings/{meeting_id}/audio",
        files={"file": (f"meeting{extension}", content, content_type)},
    )
    response_data = response.json()

    assert response.status_code == 201
    assert response_data["meeting_id"] == meeting_id
    assert response_data["content_type"] == content_type
    assert response_data["size_bytes"] == len(content)
    assert response_data["status"] == "uploaded"
    assert Path(response_data["filename"]).suffix == extension
    assert (audio_storage_root / meeting_id / response_data["filename"]).is_file()

    meeting_response = client.get(f"/api/v1/meetings/{meeting_id}")
    assert meeting_response.json()["status"] == "uploaded"
    assert meeting_response.json()["audio_filename"] == response_data["filename"]


def test_upload_rejects_unsupported_extension(audio_storage_root: Path) -> None:
    meeting_id = create_meeting()

    response = client.post(
        f"/api/v1/meetings/{meeting_id}/audio",
        files={"file": ("meeting.txt", b"not audio", "text/plain")},
    )

    assert response.status_code == 415
    assert not audio_storage_root.exists()


def test_upload_rejects_empty_file(audio_storage_root: Path) -> None:
    meeting_id = create_meeting()

    response = client.post(
        f"/api/v1/meetings/{meeting_id}/audio",
        files={"file": ("meeting.mp3", b"", "audio/mpeg")},
    )

    assert response.status_code == 400
    assert list(audio_storage_root.rglob("*.mp3")) == []


def test_upload_rejects_file_larger_than_limit(
    tmp_path: Path,
    audio_storage_root: Path,
) -> None:
    meeting_id = create_meeting()
    source = tmp_path / "large-audio.mp3"
    with source.open("wb") as large_audio:
        large_audio.seek(MAX_UPLOAD_SIZE_BYTES)
        large_audio.write(b"x")

    with source.open("rb") as large_audio:
        response = client.post(
            f"/api/v1/meetings/{meeting_id}/audio",
            files={"file": ("large-audio.mp3", large_audio, "audio/mpeg")},
        )

    assert response.status_code == 413
    assert list(audio_storage_root.rglob("*.mp3")) == []


def test_upload_returns_404_for_unknown_meeting(audio_storage_root: Path) -> None:
    response = client.post(
        f"/api/v1/meetings/{uuid4()}/audio",
        files={"file": ("meeting.mp3", b"audio", "audio/mpeg")},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Meeting not found"}
    assert not audio_storage_root.exists()
