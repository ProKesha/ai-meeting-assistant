from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator


class ActionItem(BaseModel):
    task: str
    assignee: str | None
    deadline: str | None
    priority: Literal["low", "medium", "high"] = "medium"


class MeetingAnalysis(BaseModel):
    summary: str
    decisions: list[str]
    action_items: list[ActionItem]
    open_questions: list[str]


class MeetingAnalysisRequest(BaseModel):
    transcript: str

    @field_validator("transcript")
    @classmethod
    def reject_blank_transcript(cls, transcript: str) -> str:
        if not transcript.strip():
            raise ValueError("transcript must not be empty")
        return transcript


class MeetingAnalysisResponse(BaseModel):
    meeting_id: UUID
    analysis: MeetingAnalysis
    model: str
    status: Literal["completed"]
