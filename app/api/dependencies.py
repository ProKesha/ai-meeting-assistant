from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.repositories.meetings import MeetingRepository
from app.services.analysis import AnalysisService, get_analysis_service
from app.services.audio_storage import AudioStorage, get_audio_storage
from app.services.embedding import EmbeddingService, get_embedding_service
from app.services.meeting_processing import MeetingProcessingService
from app.services.rag import RAGAnswerService, RAGService, get_rag_answer_service
from app.services.semantic_search import SemanticSearchService
from app.services.transcription import TranscriptionService, get_transcription_service


def get_meeting_repository(
    session: AsyncSession = Depends(get_db_session),
) -> MeetingRepository:
    return MeetingRepository(session)


def get_meeting_processing_service(
    repository: MeetingRepository = Depends(get_meeting_repository),
    audio_storage: AudioStorage = Depends(get_audio_storage),
    transcription_service: TranscriptionService = Depends(get_transcription_service),
    analysis_service: AnalysisService = Depends(get_analysis_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> MeetingProcessingService:
    return MeetingProcessingService(
        audio_storage=audio_storage,
        transcription_service=transcription_service,
        analysis_service=analysis_service,
        embedding_service=embedding_service,
        repository=repository,
    )


def get_semantic_search_service(
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    repository: MeetingRepository = Depends(get_meeting_repository),
) -> SemanticSearchService:
    return SemanticSearchService(
        embedding_service=embedding_service,
        repository=repository,
    )


def get_rag_service(
    search_service: SemanticSearchService = Depends(get_semantic_search_service),
    answer_service: RAGAnswerService = Depends(get_rag_answer_service),
) -> RAGService:
    return RAGService(
        search_service=search_service,
        answer_service=answer_service,
    )
