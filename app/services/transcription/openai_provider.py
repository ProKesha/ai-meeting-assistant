import logging
from pathlib import Path

from openai import OpenAI, OpenAIError

from app.core.config import Settings
from app.services.transcription.base import TranscriptionProviderUnavailableError

logger = logging.getLogger(__name__)


class OpenAITranscriptionProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def model(self) -> str:
        return self._settings.openai_transcription_model

    def transcribe(self, audio_path: Path) -> str:
        api_key = (
            self._settings.openai_api_key.get_secret_value()
            if self._settings.openai_api_key is not None
            else None
        )

        try:
            client = OpenAI(api_key=api_key)
            with audio_path.open("rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                )
        except OpenAIError as exc:
            logger.exception("OpenAI transcription request failed")
            raise TranscriptionProviderUnavailableError("OpenAI transcription failed") from exc

        return transcription.text
