from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.analysis import MeetingAnalysis
from app.services.audio_storage import ALLOWED_AUDIO_EXTENSIONS


class MeetingCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None


class MeetingResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: str


class MeetingDetailResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: str
    audio_filename: str | None
    transcript: str | None
    analysis: MeetingAnalysis | None
    transcription_model: str | None
    analysis_model: str | None
    created_at: datetime
    updated_at: datetime


class MeetingListItemResponse(BaseModel):
    id: UUID
    title: str
    status: str
    created_at: datetime
    summary: str | None


class AudioUploadResponse(BaseModel):
    meeting_id: UUID
    filename: str
    content_type: str | None
    size_bytes: int
    status: str


class TranscriptionRequest(BaseModel):
    filename: str

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, filename: str) -> str:
        path = Path(filename)
        if (
            not filename
            or path.is_absolute()
            or path.name != filename
            or "/" in filename
            or "\\" in filename
        ):
            raise ValueError("filename must not contain a filesystem path")

        if path.suffix.lower() not in ALLOWED_AUDIO_EXTENSIONS:
            raise ValueError("filename must use a supported audio extension")

        try:
            UUID(path.stem)
        except ValueError as exc:
            raise ValueError("filename must use the server-generated UUID format") from exc

        return filename


class TranscriptionResponse(BaseModel):
    meeting_id: UUID
    text: str
    model: str
    status: str
