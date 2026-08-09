from uuid import UUID

from pydantic import BaseModel, Field, field_validator


MAX_SEARCH_RESULTS = 20


class SemanticSearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=MAX_SEARCH_RESULTS)
    meeting_id: UUID | None = None

    @field_validator("query")
    @classmethod
    def reject_blank_query(cls, query: str) -> str:
        stripped_query = query.strip()
        if not stripped_query:
            raise ValueError("query must not be empty")
        return stripped_query


class SemanticSearchResultResponse(BaseModel):
    chunk_id: UUID
    meeting_id: UUID
    meeting_title: str
    chunk_index: int
    content: str
    similarity: float


class SemanticSearchResponse(BaseModel):
    query: str
    results: list[SemanticSearchResultResponse]
