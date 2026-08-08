import logging
from collections.abc import Callable
from pathlib import Path
from threading import Lock

from faster_whisper import WhisperModel

from app.services.transcription.base import TranscriptionProviderError

logger = logging.getLogger(__name__)


class LocalWhisperProvider:
    def __init__(
        self,
        model_name: str,
        device: str,
        compute_type: str,
        model_factory: Callable[..., WhisperModel] = WhisperModel,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._compute_type = compute_type
        self._model_factory = model_factory
        self._whisper_model: WhisperModel | None = None
        self._model_lock = Lock()

    @property
    def model(self) -> str:
        return f"faster-whisper:{self._model_name}"

    def _get_model(self) -> WhisperModel:
        if self._whisper_model is None:
            with self._model_lock:
                if self._whisper_model is None:
                    self._whisper_model = self._model_factory(
                        self._model_name,
                        device=self._device,
                        compute_type=self._compute_type,
                    )
        return self._whisper_model

    def transcribe(self, audio_path: Path) -> str:
        try:
            whisper_model = self._get_model()
            segments, _ = whisper_model.transcribe(str(audio_path))
            return " ".join(
                segment.text.strip()
                for segment in segments
                if segment.text.strip()
            )
        except Exception as exc:
            logger.exception("Local faster-whisper transcription failed")
            raise TranscriptionProviderError("Local transcription failed") from exc
