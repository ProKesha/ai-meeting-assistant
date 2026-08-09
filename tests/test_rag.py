import asyncio
import json
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_rag_service
from app.main import app
from app.models.rag import RAGAnswerPayload
from app.repositories.meetings import TranscriptChunkSearchResult
from app.services.embedding import (
    EmbeddingServiceError,
    EmbeddingServiceUnavailableError,
)
from app.services.rag import (
    INSUFFICIENT_INFORMATION_ANSWER,
    OllamaRAGProvider,
    RAGAnswerService,
    RAGResult,
    RAGService,
    RAGServiceInvalidResponseError,
    RAGServiceUnavailableError,
    build_rag_context,
)
from app.services.semantic_search import SemanticSearchServiceError

client = TestClient(app)


def make_source(
    *,
    meeting_title: str,
    content: str,
    chunk_index: int,
    similarity: float,
) -> TranscriptChunkSearchResult:
    return TranscriptChunkSearchResult(
        chunk_id=uuid4(),
        meeting_id=uuid4(),
        meeting_title=meeting_title,
        chunk_index=chunk_index,
        content=content,
        similarity=similarity,
    )


class StubSearchService:
    def __init__(
        self,
        sources: list[TranscriptChunkSearchResult] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.sources = sources or []
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
        return self.sources


class StubAnswerService:
    def __init__(
        self,
        answer: str = "The team decided to launch on Monday.",
        error: Exception | None = None,
    ) -> None:
        self.result = answer
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def answer(self, question: str, context: str) -> str:
        self.calls.append((question, context))
        if self.error is not None:
            raise self.error
        return self.result


class StubRAGService:
    def __init__(
        self,
        result: RAGResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result or RAGResult(
            answer=INSUFFICIENT_INFORMATION_ANSWER,
            sources=(),
        )
        self.error = error
        self.calls: list[tuple[str, int, UUID | None]] = []

    async def ask(
        self,
        question: str,
        *,
        limit: int,
        meeting_id: UUID | None = None,
    ) -> RAGResult:
        self.calls.append((question, limit, meeting_id))
        if self.error is not None:
            raise self.error
        return self.result


def test_context_builder_includes_only_required_source_metadata_and_content() -> None:
    source = make_source(
        meeting_title="Product Planning",
        content="The team decided to launch the product on Monday.",
        chunk_index=3,
        similarity=0.91,
    )

    context = build_rag_context([source])

    assert context == (
        "[Source 1]\n"
        "Meeting: Product Planning\n"
        f"Meeting ID: {source.meeting_id}\n"
        "Chunk: 3\n"
        "Content:\n"
        "The team decided to launch the product on Monday."
    )
    assert "embedding" not in context.lower()
    assert "similarity" not in context.lower()


def test_rag_service_retrieves_builds_context_and_preserves_sources() -> None:
    meeting_filter = uuid4()
    sources = [
        make_source(
            meeting_title="Product Planning",
            content="The team decided to launch the product on Monday.",
            chunk_index=3,
            similarity=0.91,
        ),
        make_source(
            meeting_title="Hiring Sync",
            content="The backend interview is scheduled for Thursday.",
            chunk_index=0,
            similarity=0.42,
        ),
    ]
    search_service = StubSearchService(sources)
    answer_service = StubAnswerService()
    service = RAGService(search_service, answer_service)  # type: ignore[arg-type]

    result = asyncio.run(
        service.ask(
            "When are we launching the product?",
            limit=2,
            meeting_id=meeting_filter,
        )
    )

    assert result.answer == "The team decided to launch on Monday."
    assert result.sources == tuple(sources)
    assert search_service.calls == [
        ("When are we launching the product?", 2, meeting_filter)
    ]
    assert answer_service.calls == [
        (
            "When are we launching the product?",
            build_rag_context(sources),
        )
    ]


def test_rag_service_returns_grounded_fallback_without_calling_llm() -> None:
    search_service = StubSearchService([])
    answer_service = StubAnswerService(answer="This must not be used")
    service = RAGService(search_service, answer_service)  # type: ignore[arg-type]

    result = asyncio.run(service.ask("Unknown fact?", limit=5))

    assert result == RAGResult(
        answer=INSUFFICIENT_INFORMATION_ANSWER,
        sources=(),
    )
    assert answer_service.calls == []


def test_rag_service_propagates_semantic_search_failure_without_llm_call() -> None:
    search_service = StubSearchService(
        error=SemanticSearchServiceError("Simulated search failure")
    )
    answer_service = StubAnswerService()
    service = RAGService(search_service, answer_service)  # type: ignore[arg-type]

    with pytest.raises(SemanticSearchServiceError):
        asyncio.run(service.ask("Question", limit=5))

    assert answer_service.calls == []


def mock_rag_answer_service(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[RAGAnswerService, httpx.Client]:
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaRAGProvider(
        base_url="http://127.0.0.1:11434",
        model="llama3.2:3b",
        client=http_client,
    )
    return RAGAnswerService(provider), http_client


def test_ollama_rag_receives_question_context_and_structured_schema() -> None:
    question = "When are we launching the product?"
    context = (
        "[Source 1]\nMeeting: Product Planning\nMeeting ID: test\n"
        "Chunk: 0\nContent:\nThe product launches on Monday."
    )

    def handler(request: httpx.Request) -> httpx.Response:
        payload: dict[str, Any] = json.loads(request.content)
        assert request.url == "http://127.0.0.1:11434/api/chat"
        assert payload["model"] == "llama3.2:3b"
        assert payload["format"] == RAGAnswerPayload.model_json_schema()
        assert payload["stream"] is False
        assert payload["think"] is False
        assert payload["options"] == {"temperature": 0}
        assert "Use ONLY the provided MEETING CONTEXT" in payload["messages"][0]["content"]
        assert question in payload["messages"][1]["content"]
        assert context in payload["messages"][1]["content"]
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {"answer": "The product launches on Monday."}
                    ),
                }
            },
        )

    service, http_client = mock_rag_answer_service(handler)
    try:
        answer = service.answer(question, context)
    finally:
        http_client.close()

    assert answer == "The product launches on Monday."


def test_rag_answer_service_maps_ollama_connection_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    service, http_client = mock_rag_answer_service(handler)
    try:
        with pytest.raises(RAGServiceUnavailableError):
            service.answer("Question", "Context")
    finally:
        http_client.close()


@pytest.mark.parametrize(
    "content",
    ["not valid JSON", json.dumps({"answer": "   "}), json.dumps({"wrong": "field"})],
)
def test_rag_answer_service_rejects_malformed_ollama_response(content: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": content}})

    service, http_client = mock_rag_answer_service(handler)
    try:
        with pytest.raises(RAGServiceInvalidResponseError):
            service.answer("Question", "Context")
    finally:
        http_client.close()


@pytest.fixture
def rag_service_override() -> StubRAGService:
    service = StubRAGService()
    app.dependency_overrides[get_rag_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_rag_service, None)


@pytest.mark.parametrize("question", ["", "   ", "\n\t"])
def test_ask_rejects_empty_or_whitespace_question(
    question: str,
    rag_service_override: StubRAGService,
) -> None:
    response = client.post("/api/v1/ask", json={"question": question})

    assert response.status_code == 422
    assert rag_service_override.calls == []


@pytest.mark.parametrize("limit", [0, -1, 21, 1000])
def test_ask_validates_limit(
    limit: int,
    rag_service_override: StubRAGService,
) -> None:
    response = client.post(
        "/api/v1/ask",
        json={"question": "When are we launching?", "limit": limit},
    )

    assert response.status_code == 422
    assert rag_service_override.calls == []


def test_ask_endpoint_returns_grounded_answer_and_retrieved_sources_only(
    rag_service_override: StubRAGService,
) -> None:
    meeting_filter = uuid4()
    source = make_source(
        meeting_title="Product Planning",
        content="The team decided to launch the product on Monday.",
        chunk_index=3,
        similarity=0.91,
    )
    rag_service_override.result = RAGResult(
        answer="The team decided to launch on Monday.",
        sources=(source,),
    )

    response = client.post(
        "/api/v1/ask",
        json={
            "question": "  When are we launching the product?  ",
            "limit": 5,
            "meeting_id": str(meeting_filter),
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "question": "When are we launching the product?",
        "answer": "The team decided to launch on Monday.",
        "sources": [
            {
                "chunk_id": str(source.chunk_id),
                "meeting_id": str(source.meeting_id),
                "meeting_title": "Product Planning",
                "chunk_index": 3,
                "similarity": 0.91,
            }
        ],
    }
    assert rag_service_override.calls == [
        ("When are we launching the product?", 5, meeting_filter)
    ]


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            EmbeddingServiceUnavailableError("Simulated model failure"),
            503,
            "Local embedding service unavailable",
        ),
        (
            EmbeddingServiceError("Simulated embedding failure"),
            500,
            "Query embedding generation failed",
        ),
        (
            SemanticSearchServiceError("Simulated search failure"),
            500,
            "Semantic search failed",
        ),
        (
            RAGServiceUnavailableError("Simulated Ollama failure"),
            503,
            "Local RAG service unavailable",
        ),
        (
            RAGServiceInvalidResponseError("Simulated invalid response"),
            502,
            "Invalid response from RAG service",
        ),
    ],
)
def test_ask_endpoint_maps_service_failures(
    error: Exception,
    expected_status: int,
    expected_detail: str,
    rag_service_override: StubRAGService,
) -> None:
    rag_service_override.error = error

    response = client.post(
        "/api/v1/ask",
        json={"question": "When are we launching?"},
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": expected_detail}
