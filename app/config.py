"""Конфигурация приложения из переменных окружения."""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Поддерживаемые режимы запуска."""

    LOCAL = "local"
    TEST = "test"
    PRODUCTION = "production"


class LlmProvider(StrEnum):
    """Поддерживаемые варианты OpenAI-совместимого API."""

    OPENAI = "openai"
    OLLAMA = "ollama"


class Settings(BaseSettings):
    """Настройки процесса приложения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="APP_",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    environment: Environment = Environment.LOCAL
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    log_level: str = "INFO"
    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://tender:tender@localhost:5432/tender_intelligence"
    )
    database_echo: bool = False
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_pool_timeout: int = Field(default=30, ge=1, le=300)
    database_connect_timeout: float = Field(default=5.0, gt=0, le=60)
    storage_path: Path = Path("storage/uploads")
    upload_max_size_mb: int = Field(default=25, ge=1, le=500)
    upload_chunk_size_bytes: int = Field(default=1024 * 1024, ge=64 * 1024, le=8 * 1024 * 1024)
    text_chunk_size_chars: int = Field(default=1200, ge=200, le=10000)
    text_chunk_overlap_chars: int = Field(default=200, ge=0, le=2000)
    analysis_context_max_chunks: int = Field(default=12, ge=1, le=50)
    analysis_context_max_chars: int = Field(default=16000, ge=1000, le=100000)
    llm_provider: LlmProvider = LlmProvider.OPENAI
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = Field(default=60, gt=0, le=300)
    embedding_model: str = "text-embedding-3-small"
    embedding_batch_size: int = Field(default=32, ge=1, le=2048)
    rag_top_k: int = Field(default=5, ge=2, le=20)
    rag_min_relevance: float = Field(default=0.15, ge=-1, le=1)

    @property
    def upload_max_size_bytes(self) -> int:
        """Вернуть ограничение размера загружаемого файла в байтах."""
        return self.upload_max_size_mb * 1024 * 1024

    @model_validator(mode="after")
    def validate_chunk_settings(self) -> "Settings":
        """Проверить, что перекрытие меньше размера фрагмента."""
        if self.text_chunk_overlap_chars >= self.text_chunk_size_chars:
            raise ValueError("Перекрытие фрагментов должно быть меньше их размера")
        return self

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Нормализовать и проверить уровень журналирования."""
        normalized = value.upper()
        allowed_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed_levels:
            message = f"Недопустимый уровень журналирования: {value}"
            raise ValueError(message)
        return normalized


@lru_cache
def get_settings() -> Settings:
    """Вернуть единственный экземпляр настроек процесса."""
    return Settings()
