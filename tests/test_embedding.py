import sys
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from types import ModuleType

import pytest

from app.db.models import TranscriptChunkRecord
from app.services.embedding import (
    EMBEDDING_DIMENSION,
    EMBEDDING_PASSAGE_PREFIX,
    EMBEDDING_QUERY_PREFIX,
    EmbeddingService,
    EmbeddingServiceError,
)


class StubSentenceEmbeddingModel:
    def __init__(
        self,
        *,
        dimension: int = EMBEDDING_DIMENSION,
        output_dimension: int = EMBEDDING_DIMENSION,
        error: Exception | None = None,
    ) -> None:
        self.dimension = dimension
        self.output_dimension = output_dimension
        self.error = error
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def get_embedding_dimension(self) -> int:
        return self.dimension

    def encode(self, sentences: list[str], **kwargs: object) -> list[list[float]]:
        self.calls.append((sentences, kwargs))
        if self.error is not None:
            raise self.error
        return [
            [float(index + 1)] * self.output_dimension
            for index, _ in enumerate(sentences)
        ]


def create_service(model: StubSentenceEmbeddingModel) -> EmbeddingService:
    return EmbeddingService(
        model_name="intfloat/multilingual-e5-small",
        device="cpu",
        model=model,
    )


def test_embedding_service_embeds_one_passage_with_correct_dimension() -> None:
    model = StubSentenceEmbeddingModel()
    service = create_service(model)

    embedding = service.embed("The launch date was approved.")

    assert len(embedding) == EMBEDDING_DIMENSION
    assert service.dimension == EMBEDDING_DIMENSION
    assert model.calls == [
        (
            [f"{EMBEDDING_PASSAGE_PREFIX}The launch date was approved."],
            {
                "normalize_embeddings": True,
                "convert_to_numpy": True,
                "show_progress_bar": False,
            },
        )
    ]


def test_embedding_service_embeds_batches_deterministically() -> None:
    model = StubSentenceEmbeddingModel()
    service = create_service(model)
    texts = ["First chunk", "Second chunk"]

    first = service.embed_many(texts)
    second = service.embed_many(texts)

    assert first == second
    assert len(first) == len(texts)
    assert all(len(embedding) == EMBEDDING_DIMENSION for embedding in first)


def test_embedding_service_uses_query_prefix_for_search_queries() -> None:
    model = StubSentenceEmbeddingModel()
    service = create_service(model)

    embedding = service.embed_query("When are we launching the product?")

    assert len(embedding) == EMBEDDING_DIMENSION
    assert model.calls == [
        (
            [f"{EMBEDDING_QUERY_PREFIX}When are we launching the product?"],
            {
                "normalize_embeddings": True,
                "convert_to_numpy": True,
                "show_progress_bar": False,
            },
        )
    ]


def test_embedding_service_handles_empty_batch_without_loading_model() -> None:
    model = StubSentenceEmbeddingModel(dimension=123)

    assert create_service(model).embed_many([]) == []
    assert model.calls == []


def test_embedding_service_loads_model_once_for_concurrent_first_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_loads = 0
    load_count_lock = Lock()
    start = Event()
    model = StubSentenceEmbeddingModel()

    def model_factory(model_name: str, *, device: str) -> StubSentenceEmbeddingModel:
        nonlocal model_loads
        assert model_name == "intfloat/multilingual-e5-small"
        assert device == "cpu"
        with load_count_lock:
            model_loads += 1
        time.sleep(0.05)
        return model

    sentence_transformers = ModuleType("sentence_transformers")
    sentence_transformers.SentenceTransformer = model_factory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", sentence_transformers)
    service = EmbeddingService(
        model_name="intfloat/multilingual-e5-small",
        device="cpu",
    )

    def embed_after_start() -> list[float]:
        start.wait()
        return service.embed("Concurrent transcript chunk")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(embed_after_start) for _ in range(2)]
        start.set()
        embeddings = [future.result() for future in futures]

    assert model_loads == 1
    assert all(len(embedding) == EMBEDDING_DIMENSION for embedding in embeddings)


def test_embedding_service_rejects_string_as_batch() -> None:
    with pytest.raises(TypeError, match="sequence of texts"):
        create_service(StubSentenceEmbeddingModel()).embed_many("Transcript chunk")


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_embedding_service_rejects_empty_text(text: str) -> None:
    with pytest.raises(EmbeddingServiceError, match="must not be empty"):
        create_service(StubSentenceEmbeddingModel()).embed(text)


def test_embedding_service_validates_model_dimension() -> None:
    service = create_service(StubSentenceEmbeddingModel(dimension=768))

    with pytest.raises(EmbeddingServiceError, match="must be 384"):
        service.embed("Transcript chunk")


def test_embedding_service_validates_output_dimension() -> None:
    service = create_service(StubSentenceEmbeddingModel(output_dimension=10))

    with pytest.raises(EmbeddingServiceError, match="invalid dimension"):
        service.embed("Transcript chunk")


def test_embedding_service_wraps_model_errors() -> None:
    service = create_service(
        StubSentenceEmbeddingModel(error=RuntimeError("Simulated model failure"))
    )

    with pytest.raises(EmbeddingServiceError, match="Could not generate embeddings"):
        service.embed("Transcript chunk")


def test_transcript_chunk_vector_has_fixed_dimension() -> None:
    vector_type = TranscriptChunkRecord.__table__.c.embedding.type

    assert vector_type.dim == EMBEDDING_DIMENSION
