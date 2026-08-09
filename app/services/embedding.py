import math
from collections.abc import Sequence
from functools import lru_cache
from threading import Lock
from typing import Protocol

from app.core.config import Settings, get_settings
from app.core.constants import EMBEDDING_DIMENSION


EMBEDDING_PASSAGE_PREFIX = "passage: "
EMBEDDING_QUERY_PREFIX = "query: "


class EmbeddingServiceError(Exception):
    pass


class EmbeddingServiceUnavailableError(EmbeddingServiceError):
    pass


class SentenceEmbeddingModel(Protocol):
    def encode(self, sentences: list[str], **kwargs: object) -> object: ...


class EmbeddingService:
    def __init__(
        self,
        model_name: str,
        device: str,
        model: SentenceEmbeddingModel | None = None,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self._model = model
        self._model_lock = Lock()

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIMENSION

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_many([text], prefix=EMBEDDING_QUERY_PREFIX)[0]

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed_many(texts, prefix=EMBEDDING_PASSAGE_PREFIX)

    def _embed_many(
        self,
        texts: Sequence[str],
        *,
        prefix: str,
    ) -> list[list[float]]:
        if isinstance(texts, str):
            raise TypeError("embed_many expects a sequence of texts")
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise EmbeddingServiceError("Embedding text must not be empty")

        model = self._get_model()
        prefixed_texts = [f"{prefix}{text}" for text in texts]

        try:
            encoded = model.encode(
                prefixed_texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            raise EmbeddingServiceError("Could not generate embeddings") from exc

        return self._validate_embeddings(encoded, expected_count=len(texts))

    def _get_model(self) -> SentenceEmbeddingModel:
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer

                        self._model = SentenceTransformer(
                            self.model_name,
                            device=self.device,
                        )
                    except Exception as exc:
                        raise EmbeddingServiceUnavailableError(
                            "Could not load the local embedding model"
                        ) from exc

        get_dimension = getattr(self._model, "get_embedding_dimension", None)
        if get_dimension is None:
            get_dimension = getattr(
                self._model,
                "get_sentence_embedding_dimension",
                None,
            )
        dimension = get_dimension() if callable(get_dimension) else None
        if dimension != EMBEDDING_DIMENSION:
            raise EmbeddingServiceError(
                f"Embedding model dimension must be {EMBEDDING_DIMENSION}, got {dimension}"
            )
        return self._model

    def _validate_embeddings(
        self,
        encoded: object,
        *,
        expected_count: int,
    ) -> list[list[float]]:
        raw_embeddings = encoded.tolist() if hasattr(encoded, "tolist") else encoded
        if not isinstance(raw_embeddings, Sequence) or isinstance(raw_embeddings, str):
            raise EmbeddingServiceError("Embedding model returned an invalid result")
        if len(raw_embeddings) != expected_count:
            raise EmbeddingServiceError(
                "Embedding model returned an unexpected number of vectors"
            )

        embeddings: list[list[float]] = []
        for raw_embedding in raw_embeddings:
            if not isinstance(raw_embedding, Sequence):
                raise EmbeddingServiceError("Embedding model returned an invalid vector")
            try:
                embedding = [float(value) for value in raw_embedding]
            except (TypeError, ValueError) as exc:
                raise EmbeddingServiceError(
                    "Embedding model returned a non-numeric vector"
                ) from exc
            if len(embedding) != EMBEDDING_DIMENSION:
                raise EmbeddingServiceError(
                    "Embedding model returned a vector with an invalid dimension"
                )
            if not all(math.isfinite(value) for value in embedding):
                raise EmbeddingServiceError(
                    "Embedding model returned a non-finite vector"
                )
            embeddings.append(embedding)

        return embeddings


def create_embedding_service(settings: Settings) -> EmbeddingService:
    return EmbeddingService(
        model_name=settings.local_embedding_model,
        device=settings.local_embedding_device,
    )


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return create_embedding_service(get_settings())
