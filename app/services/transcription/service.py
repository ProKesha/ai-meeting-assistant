from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import Settings, get_settings
from app.services.transcription.base import (
    TranscriptionProvider,
    TranscriptionProviderError,
    TranscriptionProviderUnavailableError,
)
from app.services.transcription.local_whisper_provider import LocalWhisperProvider
from app.services.transcription.openai_provider import OpenAITranscriptionProvider


class TranscriptionServiceError(Exception):
    pass


class TranscriptionServiceUnavailableError(TranscriptionServiceError):
    pass


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    model: str


class TranscriptionService:
    def __init__(self, provider: TranscriptionProvider) -> None:
        self.provider = provider

    def transcribe(self, audio_path: Path) -> TranscriptionResult:
        try:
            text = self.provider.transcribe(audio_path)
        except TranscriptionProviderUnavailableError as exc:
            raise TranscriptionServiceUnavailableError from exc
        except TranscriptionProviderError as exc:
            raise TranscriptionServiceError from exc

        return TranscriptionResult(text=text, model=self.provider.model)


def create_transcription_service(settings: Settings) -> TranscriptionService:
    if settings.transcription_provider == "openai":
        provider: TranscriptionProvider = OpenAITranscriptionProvider(settings)
    else:
        provider = LocalWhisperProvider(
            model_name=settings.local_whisper_model,
            device=settings.local_whisper_device,
            compute_type=settings.local_whisper_compute_type,
        )

    return TranscriptionService(provider)


@lru_cache
def get_transcription_service() -> TranscriptionService:
    return create_transcription_service(get_settings())
