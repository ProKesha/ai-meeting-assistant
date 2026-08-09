import asyncio
from uuid import UUID

from app.repositories.meetings import MeetingRepository, TranscriptChunkSearchResult
from app.services.embedding import EmbeddingService


class SemanticSearchServiceError(Exception):
    pass


class SemanticSearchService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        repository: MeetingRepository,
    ) -> None:
        self.embedding_service = embedding_service
        self.repository = repository

    async def search(
        self,
        query: str,
        *,
        limit: int,
        meeting_id: UUID | None = None,
    ) -> list[TranscriptChunkSearchResult]:
        query_embedding = await asyncio.to_thread(
            self.embedding_service.embed_query,
            query,
        )
        try:
            return await self.repository.search_transcript_chunks(
                query_embedding,
                limit=limit,
                meeting_id=meeting_id,
            )
        except Exception as exc:
            raise SemanticSearchServiceError("Semantic search failed") from exc
