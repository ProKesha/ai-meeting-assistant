from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ActionItemRecord, MeetingRecord, TranscriptChunkRecord
from app.models.analysis import MeetingAnalysis
from app.models.meeting import MeetingCreate


@dataclass(frozen=True)
class TranscriptChunkSearchResult:
    chunk_id: UUID
    meeting_id: UUID
    meeting_title: str
    chunk_index: int
    content: str
    similarity: float


class MeetingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, meeting: MeetingCreate) -> MeetingRecord:
        record = MeetingRecord(
            title=meeting.title,
            description=meeting.description,
            status="created",
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def get(
        self,
        meeting_id: UUID,
        *,
        include_action_items: bool = False,
    ) -> MeetingRecord | None:
        statement = select(MeetingRecord).where(MeetingRecord.id == meeting_id)
        if include_action_items:
            statement = statement.options(selectinload(MeetingRecord.action_items))

        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def list(self, *, limit: int, offset: int) -> list[MeetingRecord]:
        result = await self.session.execute(
            select(MeetingRecord)
            .order_by(MeetingRecord.created_at.desc(), MeetingRecord.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars())

    async def mark_uploaded(self, meeting: MeetingRecord, filename: str) -> None:
        meeting.audio_filename = filename
        meeting.status = "uploaded"
        await self.session.commit()

    async def set_status(self, meeting: MeetingRecord, status: str) -> None:
        meeting.status = status
        await self.session.commit()

    async def mark_processing_failed(self, meeting_id: UUID) -> None:
        try:
            await self.session.rollback()
            await self.session.execute(
                update(MeetingRecord)
                .where(MeetingRecord.id == meeting_id)
                .values(status="failed")
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def persist_processing_result(
        self,
        meeting: MeetingRecord,
        *,
        transcript: str,
        transcript_chunks: Sequence[str],
        analysis: MeetingAnalysis,
        transcription_model: str,
        analysis_model: str,
    ) -> None:
        meeting.transcript = transcript
        meeting.summary = analysis.summary
        meeting.decisions = analysis.decisions
        meeting.open_questions = analysis.open_questions
        meeting.transcription_model = transcription_model
        meeting.analysis_model = analysis_model

        await self.session.execute(
            delete(ActionItemRecord).where(ActionItemRecord.meeting_id == meeting.id)
        )
        self.session.add_all(
            [
                ActionItemRecord(
                    meeting_id=meeting.id,
                    task=item.task,
                    assignee=item.assignee,
                    deadline=item.deadline,
                    priority=item.priority,
                )
                for item in analysis.action_items
            ]
        )
        await self.replace_transcript_chunks(meeting.id, transcript_chunks)
        await self.session.commit()

    async def complete_processing_with_embeddings(
        self,
        meeting: MeetingRecord,
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        chunks = await self.get_transcript_chunks(meeting.id)
        if len(chunks) != len(embeddings):
            raise ValueError("Embedding count must match transcript chunk count")

        for chunk, embedding in zip(chunks, embeddings, strict=True):
            chunk.embedding = list(embedding)

        meeting.status = "completed"
        await self.session.commit()

    async def replace_transcript_chunks(
        self,
        meeting_id: UUID,
        chunks: Sequence[str],
    ) -> None:
        await self.session.execute(
            delete(TranscriptChunkRecord).where(
                TranscriptChunkRecord.meeting_id == meeting_id
            )
        )
        self.session.add_all(
            [
                TranscriptChunkRecord(
                    meeting_id=meeting_id,
                    chunk_index=chunk_index,
                    content=content,
                    embedding=None,
                )
                for chunk_index, content in enumerate(chunks)
            ]
        )

    async def get_transcript_chunks(
        self,
        meeting_id: UUID,
    ) -> list[TranscriptChunkRecord]:
        result = await self.session.execute(
            select(TranscriptChunkRecord)
            .where(TranscriptChunkRecord.meeting_id == meeting_id)
            .order_by(TranscriptChunkRecord.chunk_index)
        )
        return list(result.scalars())

    async def search_transcript_chunks(
        self,
        query_embedding: Sequence[float],
        *,
        limit: int,
        meeting_id: UUID | None = None,
    ) -> list[TranscriptChunkSearchResult]:
        vector_dimension = TranscriptChunkRecord.__table__.c.embedding.type.dim
        if len(query_embedding) != vector_dimension:
            raise ValueError(f"Query embedding must have {vector_dimension} dimensions")

        cosine_distance = TranscriptChunkRecord.embedding.cosine_distance(
            list(query_embedding)
        ).label("cosine_distance")
        statement = (
            select(
                TranscriptChunkRecord.id,
                TranscriptChunkRecord.meeting_id,
                MeetingRecord.title,
                TranscriptChunkRecord.chunk_index,
                TranscriptChunkRecord.content,
                cosine_distance,
            )
            .join(MeetingRecord, MeetingRecord.id == TranscriptChunkRecord.meeting_id)
            .where(TranscriptChunkRecord.embedding.is_not(None))
            .order_by(
                cosine_distance.asc(),
                TranscriptChunkRecord.meeting_id.asc(),
                TranscriptChunkRecord.chunk_index.asc(),
                TranscriptChunkRecord.id.asc(),
            )
            .limit(limit)
        )
        if meeting_id is not None:
            statement = statement.where(TranscriptChunkRecord.meeting_id == meeting_id)

        rows = (await self.session.execute(statement)).all()
        return [
            TranscriptChunkSearchResult(
                chunk_id=chunk_id,
                meeting_id=result_meeting_id,
                meeting_title=meeting_title,
                chunk_index=chunk_index,
                content=content,
                similarity=1.0 - float(distance),
            )
            for (
                chunk_id,
                result_meeting_id,
                meeting_title,
                chunk_index,
                content,
                distance,
            ) in rows
        ]


def analysis_from_record(meeting: MeetingRecord) -> MeetingAnalysis | None:
    if meeting.summary is None:
        return None
    return MeetingAnalysis(
        summary=meeting.summary,
        decisions=meeting.decisions,
        action_items=[
            {
                "task": item.task,
                "assignee": item.assignee,
                "deadline": item.deadline,
                "priority": item.priority,
            }
            for item in meeting.action_items
        ],
        open_questions=meeting.open_questions,
    )
