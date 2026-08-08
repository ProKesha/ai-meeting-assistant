from dataclasses import dataclass
from uuid import UUID

from app.models.analysis import MeetingAnalysis
from app.services.analysis import AnalysisService
from app.services.audio_storage import AudioStorage
from app.services.transcription import TranscriptionService


class InvalidMeetingAudioFilenameError(Exception):
    pass


class MeetingAudioNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class MeetingProcessResult:
    transcript: str
    analysis: MeetingAnalysis
    transcription_model: str
    analysis_model: str


class MeetingProcessingService:
    def __init__(
        self,
        audio_storage: AudioStorage,
        transcription_service: TranscriptionService,
        analysis_service: AnalysisService,
    ) -> None:
        self.audio_storage = audio_storage
        self.transcription_service = transcription_service
        self.analysis_service = analysis_service

    def process(self, meeting_id: UUID, filename: str) -> MeetingProcessResult:
        try:
            audio_path = self.audio_storage.resolve(meeting_id, filename)
        except ValueError as exc:
            raise InvalidMeetingAudioFilenameError from exc

        if not audio_path.is_file():
            raise MeetingAudioNotFoundError

        transcription = self.transcription_service.transcribe(audio_path)
        analysis = self.analysis_service.analyze(transcription.text)

        return MeetingProcessResult(
            transcript=transcription.text,
            analysis=analysis.analysis,
            transcription_model=transcription.model,
            analysis_model=analysis.model,
        )
