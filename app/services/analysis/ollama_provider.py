import json
import logging

import httpx
from pydantic import ValidationError

from app.models.analysis import MeetingAnalysis

logger = logging.getLogger("uvicorn.error")

SYSTEM_PROMPT = """You analyze meeting transcripts into concise structured results.

Preserve the transcript's factual meaning and names exactly as stated. Do not invent facts,
assignees, deadlines, decisions, tasks, or questions. Do not change future events into past
events. Use null when an assignee or deadline is unknown. Include only explicit decisions and
explicit action items. Include only questions that are explicitly present or clearly unresolved
in the transcript. Use medium priority unless urgency is clearly stated; a deadline alone does
not make an item high priority. Summarize concisely.

Return ONLY the final structured response matching the provided schema. Do not output reasoning,
analysis, or chain-of-thought. Do not place the answer in a thinking or reasoning field. Emit the
complete structured response as the assistant's final content.
"""


class OllamaUnavailableError(Exception):
    pass


class OllamaInvalidResponseError(Exception):
    pass


class OllamaAnalysisProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client

    @property
    def model(self) -> str:
        return self._model

    def analyze(self, transcript: str) -> MeetingAnalysis:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Analyze the meeting transcript below. Return ONLY the final structured "
                        "response matching the provided schema in the assistant's final content. "
                        "Do not output reasoning or place the answer in a thinking field.\n\n"
                        f"Transcript:\n{transcript}"
                    ),
                },
            ],
            "format": MeetingAnalysis.model_json_schema(),
            "stream": False,
            "think": False,
            "options": {"temperature": 0},
        }

        try:
            if self._client is None:
                with httpx.Client(timeout=120.0) as client:
                    response = client.post(f"{self._base_url}/api/chat", json=payload)
            else:
                response = self._client.post(f"{self._base_url}/api/chat", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception("Ollama meeting analysis request failed")
            raise OllamaUnavailableError("Ollama request failed") from exc

        try:
            message = response.json()["message"]
            if not isinstance(message, dict):
                raise TypeError("Ollama message is not an object")

            content = message["content"]
            if not isinstance(content, str):
                raise TypeError("Ollama message content is not a string")

            if not content.strip():
                thinking_present = "thinking" in message
                thinking_preview = (
                    str(message.get("thinking"))[:1000]
                    if thinking_present
                    else None
                )
                message_preview = json.dumps(
                    message,
                    ensure_ascii=False,
                    default=str,
                )[:2000]
                logger.error(
                    "Ollama returned empty message content: "
                    "thinking_present=%s thinking_preview=%r "
                    "message_keys=%s message_preview=%r",
                    thinking_present,
                    thinking_preview,
                    list(message.keys()),
                    message_preview,
                )
                raise OllamaInvalidResponseError("Invalid Ollama response")

            return MeetingAnalysis.model_validate_json(content)
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            logger.exception("Ollama returned invalid structured meeting analysis")
            raise OllamaInvalidResponseError("Invalid Ollama response") from exc
