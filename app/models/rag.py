from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.search import MAX_SEARCH_RESULTS


class RAGRequest(BaseModel):
    question: str
    limit: int = Field(default=5, ge=1, le=MAX_SEARCH_RESULTS)
    meeting_id: UUID | None = None

    @field_validator("question")
    @classmethod
    def reject_blank_question(cls, question: str) -> str:
        stripped_question = question.strip()
        if not stripped_question:
            raise ValueError("question must not be empty")
        return stripped_question


class RAGAnswerPayload(BaseModel):
    answer: str = Field(min_length=1)

    @field_validator("answer")
    @classmethod
    def reject_blank_answer(cls, answer: str) -> str:
        if not answer.strip():
            raise ValueError("answer must not be empty")
        return answer.strip()


class RAGSourceResponse(BaseModel):
    chunk_id: UUID
    meeting_id: UUID
    meeting_title: str
    chunk_index: int
    similarity: float


class RAGResponse(BaseModel):
    question: str
    answer: str
    sources: list[RAGSourceResponse]
