from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_semantic_search_service
from app.models.search import SemanticSearchRequest, SemanticSearchResponse
from app.services.embedding import (
    EmbeddingServiceError,
    EmbeddingServiceUnavailableError,
)
from app.services.semantic_search import SemanticSearchService, SemanticSearchServiceError

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.post("", response_model=SemanticSearchResponse)
async def semantic_search(
    request: SemanticSearchRequest,
    search_service: SemanticSearchService = Depends(get_semantic_search_service),
) -> SemanticSearchResponse:
    try:
        results = await search_service.search(
            request.query,
            limit=request.limit,
            meeting_id=request.meeting_id,
        )
    except EmbeddingServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local embedding service unavailable",
        ) from exc
    except EmbeddingServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Query embedding generation failed",
        ) from exc
    except SemanticSearchServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Semantic search failed",
        ) from exc

    return SemanticSearchResponse(
        query=request.query,
        results=[
            {
                "chunk_id": result.chunk_id,
                "meeting_id": result.meeting_id,
                "meeting_title": result.meeting_title,
                "chunk_index": result.chunk_index,
                "content": result.content,
                "similarity": result.similarity,
            }
            for result in results
        ],
    )
