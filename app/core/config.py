from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_meeting_assistant"
    )
    transcription_provider: Literal["openai", "local"] = "local"
    openai_api_key: SecretStr | None = None
    openai_transcription_model: str = "gpt-4o-mini-transcribe"
    local_whisper_model: str = "small"
    local_whisper_device: str = "cpu"
    local_whisper_compute_type: str = "int8"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_analysis_model: str = "llama3.2:3b"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
