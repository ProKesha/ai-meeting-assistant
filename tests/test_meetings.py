from uuid import UUID

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_create_meeting() -> None:
    payload = {
        "title": "Weekly Product Sync",
        "description": "Discuss product roadmap and launch blockers",
    }

    response = client.post("/api/v1/meetings", json=payload)
    response_data = response.json()

    assert response.status_code == 201
    assert response_data["title"] == payload["title"]
    assert response_data["description"] == payload["description"]
    assert UUID(response_data["id"])
    assert response_data["status"] == "created"

    stored_response = client.get(f"/api/v1/meetings/{response_data['id']}")
    assert stored_response.status_code == 200
    assert stored_response.json()["title"] == payload["title"]


def test_create_meeting_requires_title() -> None:
    response = client.post(
        "/api/v1/meetings",
        json={"description": "A meeting without a title"},
    )

    assert response.status_code == 422


def test_create_meeting_rejects_empty_title() -> None:
    response = client.post(
        "/api/v1/meetings",
        json={"title": "", "description": "A meeting with an empty title"},
    )

    assert response.status_code == 422
