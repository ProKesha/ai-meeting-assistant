import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from app.db.models import MeetingRecord
from app.models.analysis import MeetingAnalysis
from app.repositories.meetings import MeetingRepository
from app.services.analysis import AnalysisService
from app.services.audio_storage import AudioStorage
from app.services.embedding import EmbeddingService
from app.services.transcript_chunking import chunk_transcript
from app.services.transcription import TranscriptionService

logger = logging.getLogger(__name__)


class InvalidMeetingAudioFilenameError(Exception):
    pass


class MeetingAudioNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class MeetingProcessResult:
    transcript: str
    transcript_chunks: tuple[str, ...]
    analysis: MeetingAnalysis
    transcription_model: str
    analysis_model: str


class MeetingProcessingService:
    def __init__(
        self,
        audio_storage: AudioStorage,
        transcription_service: TranscriptionService,
        analysis_service: AnalysisService,
        embedding_service: EmbeddingService,
        repository: MeetingRepository,
    ) -> None:
        self.audio_storage = audio_storage
        self.transcription_service = transcription_service
        self.analysis_service = analysis_service
        self.embedding_service = embedding_service
        self.repository = repository

    async def process_and_persist(
        self,
        meeting: MeetingRecord,
        filename: str,
    ) -> MeetingProcessResult:
        meeting_id = meeting.id

        try:
            await self.repository.set_status(meeting, "processing")
            result = await asyncio.to_thread(self.process, meeting_id, filename)
            await self.repository.persist_processing_result(
                meeting,
                transcript=result.transcript,
                transcript_chunks=result.transcript_chunks,
                analysis=result.analysis,
                transcription_model=result.transcription_model,
                analysis_model=result.analysis_model,
            )
            embeddings = await asyncio.to_thread(
                self.embedding_service.embed_many,
                result.transcript_chunks,
            )
            await self.repository.complete_processing_with_embeddings(
                meeting,
                embeddings,
            )
        except Exception:
            await self._attempt_mark_failed(meeting_id)
            raise

        return result

    async def _attempt_mark_failed(self, meeting_id: UUID) -> None:
        try:
            await self.repository.mark_processing_failed(meeting_id)
        except Exception:
            logger.exception("Could not persist failed status for meeting %s", meeting_id)

    def process(self, meeting_id: UUID, filename: str) -> MeetingProcessResult:
        try:
            audio_path = self.audio_storage.resolve(meeting_id, filename)
        except ValueError as exc:
            raise InvalidMeetingAudioFilenameError from exc

        if not audio_path.is_file():
            raise MeetingAudioNotFoundError

        transcription = self.transcription_service.transcribe(audio_path)
        transcript_chunks = chunk_transcript(transcription.text)
        analysis = self.analysis_service.analyze(transcription.text)

        return MeetingProcessResult(
            transcript=transcription.text,
            transcript_chunks=tuple(transcript_chunks),
            analysis=analysis.analysis,
            transcription_model=transcription.model,
            analysis_model=analysis.model,
        )
