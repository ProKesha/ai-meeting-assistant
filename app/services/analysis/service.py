from dataclasses import dataclass
from functools import lru_cache

from app.core.config import get_settings
from app.models.analysis import MeetingAnalysis
from app.services.analysis.ollama_provider import (
    OllamaAnalysisProvider,
    OllamaInvalidResponseError,
    OllamaUnavailableError,
)


class AnalysisServiceUnavailableError(Exception):
    pass


class AnalysisServiceInvalidResponseError(Exception):
    pass


@dataclass(frozen=True)
class AnalysisResult:
    analysis: MeetingAnalysis
    model: str


class AnalysisService:
    def __init__(self, provider: OllamaAnalysisProvider) -> None:
        self.provider = provider

    def analyze(self, transcript: str) -> AnalysisResult:
        try:
            analysis = self.provider.analyze(transcript)
        except OllamaUnavailableError as exc:
            raise AnalysisServiceUnavailableError from exc
        except OllamaInvalidResponseError as exc:
            raise AnalysisServiceInvalidResponseError from exc

        return AnalysisResult(analysis=analysis, model=self.provider.model)


@lru_cache
def get_analysis_service() -> AnalysisService:
    settings = get_settings()
    provider = OllamaAnalysisProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_analysis_model,
    )
    return AnalysisService(provider)
