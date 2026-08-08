from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.models.analysis import MeetingAnalysis
from app.models.meeting import TranscriptionRequest


class MeetingProcessRequest(TranscriptionRequest):
    pass


class MeetingProcessResponse(BaseModel):
    meeting_id: UUID
    transcript: str
    analysis: MeetingAnalysis
    transcription_model: str
    analysis_model: str
    status: Literal["completed"]
