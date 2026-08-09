import json
import logging
from typing import TypeVar

import httpx
from pydantic import BaseModel

logger = logging.getLogger("uvicorn.error")

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class OllamaUnavailableError(Exception):
    pass


class OllamaInvalidResponseError(Exception):
    pass


class OllamaChatClient:
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

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[ResponseModel],
    ) -> ResponseModel:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "format": response_model.model_json_schema(),
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
            logger.exception("Ollama structured chat request failed")
            raise OllamaUnavailableError("Ollama request failed") from exc

        try:
            message = response.json()["message"]
            if not isinstance(message, dict):
                raise TypeError("Ollama message is not an object")

            content = message["content"]
            if not isinstance(content, str):
                raise TypeError("Ollama message content is not a string")

            if not content.strip():
                message_preview = json.dumps(
                    message,
                    ensure_ascii=False,
                    default=str,
                )[:2000]
                logger.error(
                    "Ollama returned empty structured content: message_preview=%r",
                    message_preview,
                )
                raise OllamaInvalidResponseError("Invalid Ollama response")

            return response_model.model_validate_json(content)
        except (KeyError, TypeError, ValueError) as exc:
            logger.exception("Ollama returned an invalid structured response")
            raise OllamaInvalidResponseError("Invalid Ollama response") from exc
