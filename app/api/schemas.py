"""Схемы общих HTTP-ответов."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Состояние процесса приложения."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"] = "ok"
    service: str
    version: str


class ReadinessResponse(BaseModel):
    """Готовность приложения принимать запросы."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ready", "not_ready"]


class ErrorResponse(BaseModel):
    """Безопасное описание ошибки."""

    model_config = ConfigDict(frozen=True)

    detail: str
    code: str
    request_id: str
