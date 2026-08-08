from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.audio_storage import AudioStorage, get_audio_storage
from app.services.transcription import (
    TranscriptionProviderError,
    TranscriptionResult,
    TranscriptionService,
    TranscriptionServiceError,
    TranscriptionServiceUnavailableError,
    get_transcription_service,
)

client = TestClient(app)


class StubTranscriptionService:
    def __init__(
        self,
        result: TranscriptionResult | None = None,
        error: TranscriptionServiceError | None = None,
    ) -> None:
        self.result = result
        self.error = error

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        if self.error is not None:
            raise self.error
        assert audio_path.is_file()
        assert self.result is not None
        return self.result


@pytest.fixture
def audio_storage_root(tmp_path: Path) -> Path:
    storage_root = tmp_path / "audio"
    app.dependency_overrides[get_audio_storage] = lambda: AudioStorage(storage_root)
    yield storage_root
    app.dependency_overrides.pop(get_audio_storage, None)
    app.dependency_overrides.pop(get_transcription_service, None)


def create_stored_audio(storage_root: Path, meeting_id: UUID, filename: str) -> Path:
    audio_path = storage_root / str(meeting_id) / filename
    audio_path.parent.mkdir(parents=True)
    audio_path.write_bytes(b"test audio")
    return audio_path


def test_transcribe_meeting_audio_successfully(
    audio_storage_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    meeting_id = uuid4()
    filename = f"{uuid4()}.mp3"
    create_stored_audio(audio_storage_root, meeting_id, filename)
    app.dependency_overrides[get_transcription_service] = lambda: StubTranscriptionService(
        TranscriptionResult(
            text="Meeting transcription...",
            model="gpt-4o-mini-transcribe",
        )
    )

    response = client.post(
        f"/api/v1/meetings/{meeting_id}/transcribe",
        json={"filename": filename},
    )
    response_data = response.json()

    assert response.status_code == 200
    assert response_data["meeting_id"] == str(meeting_id)
    assert response_data["text"] == "Meeting transcription..."
    assert response_data["model"] == "gpt-4o-mini-transcribe"
    assert response_data["status"] == "completed"


def test_transcription_returns_404_for_missing_audio(audio_storage_root: Path) -> None:
    meeting_id = uuid4()

    response = client.post(
        f"/api/v1/meetings/{meeting_id}/transcribe",
        json={"filename": f"{uuid4()}.wav"},
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "filename",
    [
        "../audio.mp3",
        "/tmp/audio.mp3",
        "folder/audio.mp3",
        "folder\\audio.mp3",
    ],
)
def test_transcription_rejects_path_filenames(
    filename: str,
    audio_storage_root: Path,
) -> None:
    response = client.post(
        f"/api/v1/meetings/{uuid4()}/transcribe",
        json={"filename": filename},
    )

    assert response.status_code == 422


def test_transcription_rejects_unsupported_extension(audio_storage_root: Path) -> None:
    response = client.post(
        f"/api/v1/meetings/{uuid4()}/transcribe",
        json={"filename": f"{uuid4()}.txt"},
    )

    assert response.status_code == 422


def test_transcription_returns_502_for_openai_failure(audio_storage_root: Path) -> None:
    meeting_id = uuid4()
    filename = f"{uuid4()}.m4a"
    create_stored_audio(audio_storage_root, meeting_id, filename)
    app.dependency_overrides[get_transcription_service] = lambda: StubTranscriptionService(
        error=TranscriptionServiceUnavailableError("Simulated OpenAI failure")
    )

    response = client.post(
        f"/api/v1/meetings/{meeting_id}/transcribe",
        json={"filename": filename},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "Transcription service unavailable"}


class StubLocalProvider:
    model = "faster-whisper:small"

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def transcribe(self, audio_path: Path) -> str:
        if self.should_fail:
            raise TranscriptionProviderError("Simulated local failure")
        assert audio_path.is_file()
        return "Local meeting transcription"


def test_local_transcription_returns_text_and_model(audio_storage_root: Path) -> None:
    meeting_id = uuid4()
    filename = f"{uuid4()}.wav"
    create_stored_audio(audio_storage_root, meeting_id, filename)
    service = TranscriptionService(StubLocalProvider())
    app.dependency_overrides[get_transcription_service] = lambda: service

    response = client.post(
        f"/api/v1/meetings/{meeting_id}/transcribe",
        json={"filename": filename},
    )

    assert response.status_code == 200
    assert response.json()["text"] == "Local meeting transcription"
    assert response.json()["model"] == "faster-whisper:small"
    assert response.json()["status"] == "completed"


def test_local_transcription_failure_returns_safe_500(audio_storage_root: Path) -> None:
    meeting_id = uuid4()
    filename = f"{uuid4()}.mp3"
    create_stored_audio(audio_storage_root, meeting_id, filename)
    service = TranscriptionService(StubLocalProvider(should_fail=True))
    app.dependency_overrides[get_transcription_service] = lambda: service

    response = client.post(
        f"/api/v1/meetings/{meeting_id}/transcribe",
        json={"filename": filename},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Transcription failed"}
