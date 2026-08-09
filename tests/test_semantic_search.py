import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.routes.search import get_semantic_search_service
from app.main import app
from app.repositories.meetings import TranscriptChunkSearchResult
from app.services.embedding import (
    EMBEDDING_DIMENSION,
    EMBEDDING_QUERY_PREFIX,
    EmbeddingService,
    EmbeddingServiceError,
    EmbeddingServiceUnavailableError,
)
from app.services.semantic_search import SemanticSearchService, SemanticSearchServiceError

client = TestClient(app)


class StubSentenceEmbeddingModel:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def get_embedding_dimension(self) -> int:
        return EMBEDDING_DIMENSION

    def encode(self, sentences: list[str], **kwargs: object) -> list[list[float]]:
        self.calls.append((sentences, kwargs))
        return [[0.25] * EMBEDDING_DIMENSION for _ in sentences]


class StubSearchRepository:
    def __init__(self, results: list[TranscriptChunkSearchResult]) -> None:
        self.results = results
        self.calls: list[tuple[list[float], int, UUID | None]] = []

    async def search_transcript_chunks(
        self,
        query_embedding: list[float],
        *,
        limit: int,
        meeting_id: UUID | None = None,
    ) -> list[TranscriptChunkSearchResult]:
        self.calls.append((query_embedding, limit, meeting_id))
        return self.results


class StubSemanticSearchService:
    def __init__(
        self,
        results: list[TranscriptChunkSearchResult] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.results = results or []
        self.error = error
        self.calls: list[tuple[str, int, UUID | None]] = []

    async def search(
        self,
        query: str,
        *,
        limit: int,
        meeting_id: UUID | None = None,
    ) -> list[TranscriptChunkSearchResult]:
        self.calls.append((query, limit, meeting_id))
        if self.error is not None:
            raise self.error
        return self.results


def make_result(
    *,
    title: str,
    content: str,
    similarity: float,
    chunk_index: int = 0,
) -> TranscriptChunkSearchResult:
    return TranscriptChunkSearchResult(
        chunk_id=uuid4(),
        meeting_id=uuid4(),
        meeting_title=title,
        chunk_index=chunk_index,
        content=content,
        similarity=similarity,
    )


def test_semantic_search_service_embeds_query_and_returns_ranked_results() -> None:
    model = StubSentenceEmbeddingModel()
    embedding_service = EmbeddingService(
        model_name="intfloat/multilingual-e5-small",
        device="cpu",
        model=model,
    )
    expected_results = [
        make_result(
            title="Product Planning",
            content="The product launches on Monday.",
            similarity=0.92,
        ),
        make_result(
            title="Marketing Sync",
            content="The marketing budget changes next quarter.",
            similarity=0.35,
        ),
    ]
    repository = StubSearchRepository(expected_results)
    service = SemanticSearchService(embedding_service, repository)  # type: ignore[arg-type]

    results = asyncio.run(
        service.search("When are we launching the product?", limit=2)
    )

    assert results == expected_results
    assert [result.similarity for result in results] == [0.92, 0.35]
    assert model.calls[0][0] == [
        f"{EMBEDDING_QUERY_PREFIX}When are we launching the product?"
    ]
    assert model.calls[0][1]["normalize_embeddings"] is True
    assert len(repository.calls[0][0]) == EMBEDDING_DIMENSION
    assert repository.calls[0][1:] == (2, None)


@pytest.fixture
def search_service_override() -> StubSemanticSearchService:
    service = StubSemanticSearchService()
    app.dependency_overrides[get_semantic_search_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_semantic_search_service, None)


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_search_rejects_empty_or_whitespace_query(
    query: str,
    search_service_override: StubSemanticSearchService,
) -> None:
    response = client.post("/api/v1/search", json={"query": query})

    assert response.status_code == 422
    assert search_service_override.calls == []


@pytest.mark.parametrize("limit", [0, -1, 21, 1000])
def test_search_validates_limit(
    limit: int,
    search_service_override: StubSemanticSearchService,
) -> None:
    response = client.post(
        "/api/v1/search",
        json={"query": "Product launch", "limit": limit},
    )

    assert response.status_code == 422
    assert search_service_override.calls == []


def test_search_endpoint_returns_meeting_metadata_and_schema(
    search_service_override: StubSemanticSearchService,
) -> None:
    meeting_id = uuid4()
    first = make_result(
        title="Product Planning",
        content="The team decided to launch the product on Monday.",
        similarity=0.91,
        chunk_index=3,
    )
    second = make_result(
        title="Hiring Sync",
        content="We discussed hiring a backend engineer.",
        similarity=0.42,
    )
    search_service_override.results = [first, second]

    response = client.post(
        "/api/v1/search",
        json={
            "query": "  What did we decide about the product launch?  ",
            "limit": 2,
            "meeting_id": str(meeting_id),
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "query": "What did we decide about the product launch?",
        "results": [
            {
                "chunk_id": str(first.chunk_id),
                "meeting_id": str(first.meeting_id),
                "meeting_title": "Product Planning",
                "chunk_index": 3,
                "content": "The team decided to launch the product on Monday.",
                "similarity": 0.91,
            },
            {
                "chunk_id": str(second.chunk_id),
                "meeting_id": str(second.meeting_id),
                "meeting_title": "Hiring Sync",
                "chunk_index": 0,
                "content": "We discussed hiring a backend engineer.",
                "similarity": 0.42,
            },
        ],
    }
    assert search_service_override.calls == [
        ("What did we decide about the product launch?", 2, meeting_id)
    ]


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            EmbeddingServiceUnavailableError("Simulated unavailable model"),
            503,
            "Local embedding service unavailable",
        ),
        (
            EmbeddingServiceError("Simulated query embedding failure"),
            500,
            "Query embedding generation failed",
        ),
        (
            SemanticSearchServiceError("Simulated database failure"),
            500,
            "Semantic search failed",
        ),
    ],
)
def test_search_handles_embedding_failures(
    error: Exception,
    expected_status: int,
    expected_detail: str,
    search_service_override: StubSemanticSearchService,
) -> None:
    search_service_override.error = error

    response = client.post(
        "/api/v1/search",
        json={"query": "When are we launching?"},
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
