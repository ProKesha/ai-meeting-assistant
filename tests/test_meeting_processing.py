import asyncio
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.models.analysis import ActionItem, MeetingAnalysis
from app.repositories.meetings import MeetingRepository
from app.services.analysis import (
    AnalysisResult,
    AnalysisServiceInvalidResponseError,
    AnalysisServiceUnavailableError,
    get_analysis_service,
)
from app.services.audio_storage import AudioStorage, get_audio_storage
from app.services.embedding import (
    EMBEDDING_DIMENSION,
    EmbeddingServiceError,
    EmbeddingServiceUnavailableError,
    get_embedding_service,
)
from app.services.transcription import (
    TranscriptionResult,
    TranscriptionServiceError,
    get_transcription_service,
)

client = TestClient(app)

TRANSCRIPT = "We decided to launch on Monday. Dmytro will finish the API by Friday."

ANALYSIS = MeetingAnalysis(
    summary="The team scheduled the launch and assigned API work.",
    decisions=["Launch the product on Monday"],
    action_items=[
        ActionItem(
            task="Finish API integration",
            assignee="Dmytro",
            deadline="Friday",
            priority="medium",
        )
    ],
    open_questions=[],
)


def create_meeting() -> UUID:
    response = client.post("/api/v1/meetings", json={"title": "Processing test"})
    assert response.status_code == 201
    return UUID(response.json()["id"])


class StubTranscriptionService:
    def __init__(self, error: Exception | None = None, text: str = TRANSCRIPT) -> None:
        self.error = error
        self.text = text

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        if self.error is not None:
            raise self.error
        assert audio_path.is_file()
        return TranscriptionResult(
            text=self.text,
            model="faster-whisper:small",
        )


class StubAnalysisService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.transcripts: list[str] = []

    def analyze(self, transcript: str) -> AnalysisResult:
        if self.error is not None:
            raise self.error
        self.transcripts.append(transcript)
        return AnalysisResult(analysis=ANALYSIS, model="llama3.2:3b")


class StubEmbeddingService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.text_batches: list[list[str]] = []

    def embed_many(self, texts: tuple[str, ...]) -> list[list[float]]:
        self.text_batches.append(list(texts))
        if self.error is not None:
            raise self.error
        return [
            [float((sum(text.encode()) % 10) + 1)] * EMBEDDING_DIMENSION
            for text in texts
        ]


@pytest.fixture
def processing_dependencies(
    tmp_path: Path,
) -> tuple[Path, StubAnalysisService, StubEmbeddingService]:
    storage_root = tmp_path / "audio"
    analysis_service = StubAnalysisService()
    embedding_service = StubEmbeddingService()
    app.dependency_overrides[get_audio_storage] = lambda: AudioStorage(storage_root)
    app.dependency_overrides[get_transcription_service] = lambda: StubTranscriptionService()
    app.dependency_overrides[get_analysis_service] = lambda: analysis_service
    app.dependency_overrides[get_embedding_service] = lambda: embedding_service
    yield storage_root, analysis_service, embedding_service
    app.dependency_overrides.pop(get_audio_storage, None)
    app.dependency_overrides.pop(get_transcription_service, None)
    app.dependency_overrides.pop(get_analysis_service, None)
    app.dependency_overrides.pop(get_embedding_service, None)


def create_audio(storage_root: Path, meeting_id: UUID, filename: str) -> None:
    audio_path = storage_root / str(meeting_id) / filename
    audio_path.parent.mkdir(parents=True)
    audio_path.write_bytes(b"test audio")


def test_process_meeting_successfully(
    processing_dependencies: tuple[Path, StubAnalysisService, StubEmbeddingService],
    isolated_database: async_sessionmaker[AsyncSession],
) -> None:
    storage_root, analysis_service, embedding_service = processing_dependencies
    meeting_id = create_meeting()
    filename = f"{uuid4()}.mp3"
    create_audio(storage_root, meeting_id, filename)

    response = client.post(
        f"/api/v1/meetings/{meeting_id}/process",
        json={"filename": filename},
    )
    response_data = response.json()

    assert response.status_code == 200
    assert response_data["meeting_id"] == str(meeting_id)
    assert response_data["transcript"] == TRANSCRIPT
    assert response_data["analysis"] == ANALYSIS.model_dump(mode="json")
    assert response_data["transcription_model"] == "faster-whisper:small"
    assert response_data["analysis_model"] == "llama3.2:3b"
    assert response_data["status"] == "completed"
    assert analysis_service.transcripts == [response_data["transcript"]]
    assert embedding_service.text_batches == [[TRANSCRIPT]]

    stored_response = client.get(f"/api/v1/meetings/{meeting_id}")
    stored = stored_response.json()
    assert stored_response.status_code == 200
    assert stored["status"] == "completed"
    assert stored["transcript"] == response_data["transcript"]
    assert stored["analysis"] == ANALYSIS.model_dump(mode="json")
    assert stored["transcription_model"] == "faster-whisper:small"
    assert stored["analysis_model"] == "llama3.2:3b"

    async def load_embedding() -> list[float]:
        async with isolated_database() as session:
            chunks = await MeetingRepository(session).get_transcript_chunks(meeting_id)
            assert len(chunks) == 1
            assert chunks[0].embedding is not None
            return list(chunks[0].embedding)

    assert len(asyncio.run(load_embedding())) == EMBEDDING_DIMENSION


def test_process_meeting_returns_404_for_missing_audio(
    processing_dependencies: tuple[Path, StubAnalysisService, StubEmbeddingService],
) -> None:
    meeting_id = create_meeting()
    response = client.post(
        f"/api/v1/meetings/{meeting_id}/process",
        json={"filename": f"{uuid4()}.wav"},
    )

    assert response.status_code == 404


@pytest.mark.parametrize("filename", ["../meeting.mp3", f"{uuid4()}.txt"])
def test_process_meeting_rejects_invalid_filename(
    filename: str,
    processing_dependencies: tuple[Path, StubAnalysisService, StubEmbeddingService],
) -> None:
    meeting_id = create_meeting()
    response = client.post(
        f"/api/v1/meetings/{meeting_id}/process",
        json={"filename": filename},
    )

    assert response.status_code == 422


def test_process_meeting_returns_safe_transcription_failure(
    processing_dependencies: tuple[Path, StubAnalysisService, StubEmbeddingService],
) -> None:
    storage_root, _, _ = processing_dependencies
    meeting_id = create_meeting()
    filename = f"{uuid4()}.m4a"
    create_audio(storage_root, meeting_id, filename)
    app.dependency_overrides[get_transcription_service] = lambda: StubTranscriptionService(
        error=TranscriptionServiceError("Simulated transcription failure")
    )

    response = client.post(
        f"/api/v1/meetings/{meeting_id}/process",
        json={"filename": filename},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Transcription failed"}
    assert client.get(f"/api/v1/meetings/{meeting_id}").json()["status"] == "failed"


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            AnalysisServiceUnavailableError("Simulated unavailable Ollama"),
            503,
            "Local analysis service unavailable",
        ),
        (
            AnalysisServiceInvalidResponseError("Simulated malformed response"),
            502,
            "Invalid response from analysis service",
        ),
    ],
)
def test_process_meeting_propagates_analysis_failures(
    error: Exception,
    expected_status: int,
    expected_detail: str,
    processing_dependencies: tuple[Path, StubAnalysisService, StubEmbeddingService],
) -> None:
    storage_root, _, _ = processing_dependencies
    meeting_id = create_meeting()
    filename = f"{uuid4()}.mp3"
    create_audio(storage_root, meeting_id, filename)
    app.dependency_overrides[get_analysis_service] = lambda: StubAnalysisService(error=error)

    response = client.post(
        f"/api/v1/meetings/{meeting_id}/process",
        json={"filename": filename},
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    assert client.get(f"/api/v1/meetings/{meeting_id}").json()["status"] == "failed"


def test_reprocessing_replaces_action_items(
    processing_dependencies: tuple[Path, StubAnalysisService, StubEmbeddingService],
    isolated_database: async_sessionmaker[AsyncSession],
) -> None:
    storage_root, _, _ = processing_dependencies
    meeting_id = create_meeting()
    filename = f"{uuid4()}.mp3"
    create_audio(storage_root, meeting_id, filename)

    first = client.post(
        f"/api/v1/meetings/{meeting_id}/process",
        json={"filename": filename},
    )
    second = client.post(
        f"/api/v1/meetings/{meeting_id}/process",
        json={"filename": filename},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    stored = client.get(f"/api/v1/meetings/{meeting_id}").json()
    assert len(stored["analysis"]["action_items"]) == 1

    async def load_chunks() -> list[tuple[int, str, list[float] | None]]:
        async with isolated_database() as session:
            chunks = await MeetingRepository(session).get_transcript_chunks(meeting_id)
            return [
                (
                    chunk.chunk_index,
                    chunk.content,
                    list(chunk.embedding) if chunk.embedding is not None else None,
                )
                for chunk in chunks
            ]

    chunks = asyncio.run(load_chunks())
    assert len(chunks) == 1
    assert chunks[0][0:2] == (0, TRANSCRIPT)
    assert chunks[0][2] is not None
    assert len(chunks[0][2]) == EMBEDDING_DIMENSION


def test_processing_embeds_every_transcript_chunk(
    processing_dependencies: tuple[Path, StubAnalysisService, StubEmbeddingService],
    isolated_database: async_sessionmaker[AsyncSession],
) -> None:
    storage_root, _, embedding_service = processing_dependencies
    meeting_id = create_meeting()
    filename = f"{uuid4()}.mp3"
    create_audio(storage_root, meeting_id, filename)
    long_transcript = " ".join(f"meeting-topic-{index}" for index in range(250))
    app.dependency_overrides[get_transcription_service] = lambda: StubTranscriptionService(
        text=long_transcript
    )

    response = client.post(
        f"/api/v1/meetings/{meeting_id}/process",
        json={"filename": filename},
    )

    assert response.status_code == 200

    async def load_chunks() -> list[tuple[str, int | None]]:
        async with isolated_database() as session:
            chunks = await MeetingRepository(session).get_transcript_chunks(meeting_id)
            return [
                (
                    chunk.content,
                    len(chunk.embedding) if chunk.embedding is not None else None,
                )
                for chunk in chunks
            ]

    chunks = asyncio.run(load_chunks())
    assert len(chunks) > 1
    assert embedding_service.text_batches == [[content for content, _ in chunks]]
    assert all(dimension == EMBEDDING_DIMENSION for _, dimension in chunks)


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            EmbeddingServiceUnavailableError("Simulated unavailable model"),
            503,
            "Local embedding service unavailable",
        ),
        (
            EmbeddingServiceError("Simulated embedding failure"),
            500,
            "Embedding generation failed",
        ),
    ],
)
def test_process_meeting_marks_embedding_failures_as_failed(
    error: Exception,
    expected_status: int,
    expected_detail: str,
    processing_dependencies: tuple[Path, StubAnalysisService, StubEmbeddingService],
    isolated_database: async_sessionmaker[AsyncSession],
) -> None:
    storage_root, _, _ = processing_dependencies
    meeting_id = create_meeting()
    filename = f"{uuid4()}.mp3"
    create_audio(storage_root, meeting_id, filename)
    app.dependency_overrides[get_embedding_service] = lambda: StubEmbeddingService(
        error=error
    )

    response = client.post(
        f"/api/v1/meetings/{meeting_id}/process",
        json={"filename": filename},
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
    assert client.get(f"/api/v1/meetings/{meeting_id}").json()["status"] == "failed"

    async def load_embeddings() -> list[object]:
        async with isolated_database() as session:
            chunks = await MeetingRepository(session).get_transcript_chunks(meeting_id)
            return [chunk.embedding for chunk in chunks]

    assert asyncio.run(load_embeddings()) == [None]


def test_process_meeting_marks_persistence_failures_as_failed(
    processing_dependencies: tuple[Path, StubAnalysisService, StubEmbeddingService],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root, _, _ = processing_dependencies
    meeting_id = create_meeting()
    filename = f"{uuid4()}.mp3"
    create_audio(storage_root, meeting_id, filename)

    async def fail_persistence(*args: object, **kwargs: object) -> None:
        raise SQLAlchemyError("Simulated persistence failure")

    monkeypatch.setattr(
        MeetingRepository,
        "persist_processing_result",
        fail_persistence,
    )

    response = client.post(
        f"/api/v1/meetings/{meeting_id}/process",
        json={"filename": filename},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Meeting persistence failed"}
    assert client.get(f"/api/v1/meetings/{meeting_id}").json()["status"] == "failed"
