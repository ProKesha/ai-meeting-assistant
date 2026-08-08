from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ActionItemRecord, MeetingRecord
from app.models.analysis import MeetingAnalysis
from app.models.meeting import MeetingCreate
from app.services.meeting_processing import MeetingProcessResult


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

    async def get(self, meeting_id: UUID) -> MeetingRecord | None:
        result = await self.session.execute(
            select(MeetingRecord)
            .options(selectinload(MeetingRecord.action_items))
            .where(MeetingRecord.id == meeting_id)
        )
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
        await self.session.refresh(meeting)

    async def set_status(self, meeting: MeetingRecord, status: str) -> None:
        meeting.status = status
        await self.session.commit()
        await self.session.refresh(meeting)

    async def persist_processing_result(
        self,
        meeting: MeetingRecord,
        result: MeetingProcessResult,
    ) -> None:
        meeting.transcript = result.transcript
        meeting.summary = result.analysis.summary
        meeting.decisions = result.analysis.decisions
        meeting.open_questions = result.analysis.open_questions
        meeting.transcription_model = result.transcription_model
        meeting.analysis_model = result.analysis_model
        meeting.status = "completed"

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
                for item in result.analysis.action_items
            ]
        )
        await self.session.commit()
        await self.session.refresh(meeting)


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
