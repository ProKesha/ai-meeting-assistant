import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.meeting import MeetingCreate
from app.repositories.meetings import MeetingRepository
from app.services.embedding import EMBEDDING_DIMENSION


def test_repository_persists_replaces_and_orders_transcript_chunks(
    isolated_database: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise_repository() -> None:
        async with isolated_database() as session:
            repository = MeetingRepository(session)
            meeting = await repository.create(MeetingCreate(title="Chunk persistence"))

            await repository.replace_transcript_chunks(
                meeting.id,
                ["First chunk", "Second chunk", "Third chunk"],
            )
            await session.commit()

            stored = await repository.get_transcript_chunks(meeting.id)
            assert [chunk.chunk_index for chunk in stored] == [0, 1, 2]
            assert [chunk.content for chunk in stored] == [
                "First chunk",
                "Second chunk",
                "Third chunk",
            ]
            assert all(chunk.embedding is None for chunk in stored)

            embeddings = [
                [float(index + 1)] * EMBEDDING_DIMENSION
                for index in range(len(stored))
            ]
            await repository.complete_processing_with_embeddings(meeting, embeddings)

            embedded = await repository.get_transcript_chunks(meeting.id)
            assert meeting.status == "completed"
            assert all(
                chunk.embedding is not None
                and len(chunk.embedding) == EMBEDDING_DIMENSION
                for chunk in embedded
            )

            await repository.replace_transcript_chunks(
                meeting.id,
                ["Replacement first", "Replacement second"],
            )
            await session.commit()

            replaced = await repository.get_transcript_chunks(meeting.id)
            assert [chunk.chunk_index for chunk in replaced] == [0, 1]
            assert [chunk.content for chunk in replaced] == [
                "Replacement first",
                "Replacement second",
            ]

    asyncio.run(exercise_repository())
