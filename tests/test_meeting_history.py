import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.models.meeting import MeetingCreate
from app.repositories.meetings import MeetingRepository

client = TestClient(app)


def create_meeting(title: str) -> dict[str, object]:
    response = client.post("/api/v1/meetings", json={"title": title})
    assert response.status_code == 201
    return response.json()


def test_get_unknown_meeting_returns_404() -> None:
    response = client.get("/api/v1/meetings/2b6a749c-c83d-4b1b-8607-2192ce1feb13")

    assert response.status_code == 404
    assert response.json() == {"detail": "Meeting not found"}


def test_list_meetings_returns_newest_first_without_transcript() -> None:
    first = create_meeting("First meeting")
    second = create_meeting("Second meeting")
    third = create_meeting("Third meeting")

    response = client.get("/api/v1/meetings")

    assert response.status_code == 200
    meetings = response.json()
    assert [meeting["id"] for meeting in meetings] == [third["id"], second["id"], first["id"]]
    assert all("transcript" not in meeting for meeting in meetings)


def test_list_meetings_supports_limit_and_offset() -> None:
    create_meeting("First meeting")
    second = create_meeting("Second meeting")
    create_meeting("Third meeting")

    response = client.get("/api/v1/meetings?limit=1&offset=1")

    assert response.status_code == 200
    assert [meeting["id"] for meeting in response.json()] == [second["id"]]


def test_list_meetings_validates_pagination() -> None:
    assert client.get("/api/v1/meetings?limit=0").status_code == 422
    assert client.get("/api/v1/meetings?limit=101").status_code == 422
    assert client.get("/api/v1/meetings?offset=-1").status_code == 422


def test_repository_loads_action_items_only_for_meeting_detail(
    isolated_database: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise_repository() -> None:
        async with isolated_database() as session:
            meeting = await MeetingRepository(session).create(
                MeetingCreate(title="Relationship loading")
            )
            meeting_id = meeting.id

        async with isolated_database() as session:
            record = await MeetingRepository(session).get(meeting_id)
            assert record is not None
            assert "action_items" in inspect(record).unloaded

        async with isolated_database() as session:
            record = await MeetingRepository(session).get(
                meeting_id,
                include_action_items=True,
            )
            assert record is not None
            assert "action_items" not in inspect(record).unloaded

    asyncio.run(exercise_repository())
