from fastapi.testclient import TestClient

from app.main import app

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
