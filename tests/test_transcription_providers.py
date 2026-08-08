from pathlib import Path

from app.core.config import Settings
from app.services.transcription import (
    LocalWhisperProvider,
    OpenAITranscriptionProvider,
    create_transcription_service,
)


def test_local_provider_selected_from_settings() -> None:
    settings = Settings(_env_file=None, transcription_provider="local")

    service = create_transcription_service(settings)

    assert isinstance(service.provider, LocalWhisperProvider)


def test_openai_provider_selected_from_settings() -> None:
    settings = Settings(_env_file=None, transcription_provider="openai")

    service = create_transcription_service(settings)

    assert isinstance(service.provider, OpenAITranscriptionProvider)


def test_local_provider_loads_model_lazily_and_reuses_it(tmp_path: Path) -> None:
    model_loads = 0
    transcription_calls = 0

    class Segment:
        def __init__(self, text: str) -> None:
            self.text = text

    class FakeWhisperModel:
        def transcribe(self, audio_path: str) -> tuple[list[Segment], None]:
            nonlocal transcription_calls
            transcription_calls += 1
            assert audio_path == str(tmp_path / "audio.wav")
            return [Segment(" Hello "), Segment("world ")], None

    def model_factory(model_name: str, *, device: str, compute_type: str) -> FakeWhisperModel:
        nonlocal model_loads
        model_loads += 1
        assert model_name == "small"
        assert device == "cpu"
        assert compute_type == "int8"
        return FakeWhisperModel()

    provider = LocalWhisperProvider(
        model_name="small",
        device="cpu",
        compute_type="int8",
        model_factory=model_factory,
    )

    assert model_loads == 0
    assert provider.transcribe(tmp_path / "audio.wav") == "Hello world"
    assert provider.transcribe(tmp_path / "audio.wav") == "Hello world"
    assert model_loads == 1
    assert transcription_calls == 2
