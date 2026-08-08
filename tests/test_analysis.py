import json
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.analysis import MeetingAnalysis
from app.services.analysis import AnalysisService, OllamaAnalysisProvider, get_analysis_service

client = TestClient(app)

VALID_ANALYSIS = {
    "summary": "The team confirmed the product launch and assigned API integration work.",
    "decisions": ["Launch the product on Monday"],
    "action_items": [
        {
            "task": "Finish the API integration",
            "assignee": "Dmytro",
            "deadline": "Friday",
            "priority": "medium",
        }
    ],
    "open_questions": [],
}


@pytest.fixture(autouse=True)
def clear_analysis_override() -> None:
    yield
    app.dependency_overrides.pop(get_analysis_service, None)


def mock_analysis_service(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[AnalysisService, httpx.Client]:
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OllamaAnalysisProvider(
        base_url="http://127.0.0.1:11434",
        model="qwen3-vl:4b",
        client=http_client,
    )
    return AnalysisService(provider), http_client


def test_analyze_meeting_successfully() -> None:
    meeting_id = uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        payload: dict[str, Any] = json.loads(request.content)
        assert request.url == "http://127.0.0.1:11434/api/chat"
        assert payload["model"] == "qwen3-vl:4b"
        assert payload["stream"] is False
        assert payload["think"] is False
        assert payload["format"] == MeetingAnalysis.model_json_schema()
        assert payload["options"] == {"temperature": 0}
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps(VALID_ANALYSIS),
                    "thinking": json.dumps({"summary": "This must be ignored"}),
                }
            },
        )

    service, http_client = mock_analysis_service(handler)
    app.dependency_overrides[get_analysis_service] = lambda: service

    try:
        response = client.post(
            f"/api/v1/meetings/{meeting_id}/analyze",
            json={
                "transcript": (
                    "We decided to launch the product on Monday. "
                    "Dmytro will finish the API integration by Friday."
                )
            },
        )
    finally:
        http_client.close()

    response_data = response.json()
    assert response.status_code == 200
    assert response_data["meeting_id"] == str(meeting_id)
    assert response_data["model"] == "qwen3-vl:4b"
    assert response_data["status"] == "completed"
    assert response_data["analysis"]["action_items"][0] == VALID_ANALYSIS["action_items"][0]


@pytest.mark.parametrize("transcript", ["", "   \n\t"])
def test_analysis_rejects_empty_transcript(transcript: str) -> None:
    response = client.post(
        f"/api/v1/meetings/{uuid4()}/analyze",
        json={"transcript": transcript},
    )

    assert response.status_code == 422


def test_analysis_returns_503_when_ollama_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    service, http_client = mock_analysis_service(handler)
    app.dependency_overrides[get_analysis_service] = lambda: service

    try:
        response = client.post(
            f"/api/v1/meetings/{uuid4()}/analyze",
            json={"transcript": "A valid meeting transcript."},
        )
    finally:
        http_client.close()

    assert response.status_code == 503
    assert response.json() == {"detail": "Local analysis service unavailable"}


def test_analysis_returns_502_for_malformed_ollama_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "not valid JSON"}})

    service, http_client = mock_analysis_service(handler)
    app.dependency_overrides[get_analysis_service] = lambda: service

    try:
        response = client.post(
            f"/api/v1/meetings/{uuid4()}/analyze",
            json={"transcript": "A valid meeting transcript."},
        )
    finally:
        http_client.close()

    assert response.status_code == 502
    assert response.json() == {"detail": "Invalid response from analysis service"}


def test_analysis_rejects_empty_content_even_when_thinking_has_valid_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "   ",
                    "thinking": json.dumps(VALID_ANALYSIS),
                }
            },
        )

    service, http_client = mock_analysis_service(handler)
    app.dependency_overrides[get_analysis_service] = lambda: service

    try:
        response = client.post(
            f"/api/v1/meetings/{uuid4()}/analyze",
            json={"transcript": "A valid meeting transcript."},
        )
    finally:
        http_client.close()

    assert response.status_code == 502
    assert response.json() == {"detail": "Invalid response from analysis service"}


def test_analysis_returns_502_for_schema_validation_failure() -> None:
    invalid_analysis = {
        **VALID_ANALYSIS,
        "action_items": [{**VALID_ANALYSIS["action_items"][0], "priority": "urgent"}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps(invalid_analysis)}},
        )

    service, http_client = mock_analysis_service(handler)
    app.dependency_overrides[get_analysis_service] = lambda: service

    try:
        response = client.post(
            f"/api/v1/meetings/{uuid4()}/analyze",
            json={"transcript": "A valid meeting transcript."},
        )
    finally:
        http_client.close()

    assert response.status_code == 502
    assert response.json() == {"detail": "Invalid response from analysis service"}
