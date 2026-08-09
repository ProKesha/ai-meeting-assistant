import asyncio
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.meetings import MeetingRepository
from app.services.embedding import EMBEDDING_DIMENSION


class StubResult:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[object, ...]]:
        return self.rows


class CapturingSession:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows
        self.statement: object | None = None

    async def execute(self, statement: object) -> StubResult:
        self.statement = statement
        return StubResult(self.rows)


def test_repository_uses_pgvector_cosine_ranking_and_maps_metadata() -> None:
    first_chunk_id = uuid4()
    second_chunk_id = uuid4()
    first_meeting_id = uuid4()
    second_meeting_id = uuid4()
    session = CapturingSession(
        [
            (
                first_chunk_id,
                first_meeting_id,
                "Product Planning",
                3,
                "The team decided to launch the product on Monday.",
                0.1,
            ),
            (
                second_chunk_id,
                second_meeting_id,
                "Hiring Sync",
                0,
                "We discussed hiring a new backend engineer.",
                0.4,
            ),
        ]
    )
    repository = MeetingRepository(cast(AsyncSession, session))

    results = asyncio.run(
        repository.search_transcript_chunks(
            [0.0] * EMBEDDING_DIMENSION,
            limit=2,
        )
    )

    assert [result.similarity for result in results] == pytest.approx([0.9, 0.6])
    assert results[0].chunk_id == first_chunk_id
    assert results[0].meeting_id == first_meeting_id
    assert results[0].meeting_title == "Product Planning"
    assert results[0].chunk_index == 3
    assert results[0].content == "The team decided to launch the product on Monday."

    assert session.statement is not None
    sql = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "transcript_chunks.embedding <=>" in sql
    assert "transcript_chunks.embedding IS NOT NULL" in sql
    assert "JOIN meetings" in sql
    assert "ORDER BY cosine_distance ASC" in sql


def test_repository_supports_meeting_filter() -> None:
    meeting_id = uuid4()
    session = CapturingSession([])
    repository = MeetingRepository(cast(AsyncSession, session))

    results = asyncio.run(
        repository.search_transcript_chunks(
            [0.0] * EMBEDDING_DIMENSION,
            limit=5,
            meeting_id=meeting_id,
        )
    )

    assert results == []
    assert session.statement is not None
    sql = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "transcript_chunks.meeting_id =" in sql


def test_repository_rejects_wrong_query_vector_dimension() -> None:
    session = CapturingSession([])
    repository = MeetingRepository(cast(AsyncSession, session))

    with pytest.raises(ValueError, match="384 dimensions"):
        asyncio.run(repository.search_transcript_chunks([0.0] * 10, limit=5))

    assert session.statement is None
