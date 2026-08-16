"""Конфигурация приложения из переменных окружения."""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Поддерживаемые режимы запуска."""

    LOCAL = "local"
    TEST = "test"
    PRODUCTION = "production"


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
