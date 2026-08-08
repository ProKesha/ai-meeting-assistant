from pathlib import Path
from typing import Protocol


class TranscriptionProviderError(Exception):
    pass


class TranscriptionProviderUnavailableError(TranscriptionProviderError):
    pass


class TranscriptionProvider(Protocol):
    @property
    def model(self) -> str: ...

    def transcribe(self, audio_path: Path) -> str: ...
