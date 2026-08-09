from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_rag_service
from app.models.rag import RAGRequest, RAGResponse
from app.services.embedding import (
    EmbeddingServiceError,
    EmbeddingServiceUnavailableError,
)
from app.services.rag import (
    RAGService,
    RAGServiceInvalidResponseError,
    RAGServiceUnavailableError,
)
from app.services.semantic_search import SemanticSearchServiceError

router = APIRouter(prefix="/api/v1/ask", tags=["rag"])


@router.post("", response_model=RAGResponse)
async def ask_meeting_history(
    request: RAGRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> RAGResponse:
    try:
        result = await rag_service.ask(
            request.question,
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
    except RAGServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local RAG service unavailable",
        ) from exc
    except RAGServiceInvalidResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response from RAG service",
        ) from exc

    return RAGResponse(
        question=request.question,
        answer=result.answer,
        sources=[
            {
                "chunk_id": source.chunk_id,
                "meeting_id": source.meeting_id,
                "meeting_title": source.meeting_title,
                "chunk_index": source.chunk_index,
                "similarity": source.similarity,
            }
            for source in result.sources
        ],
    )
