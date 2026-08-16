"""Схемы общих HTTP-ответов."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.rag import RagAnswer


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


class DocumentResponse(BaseModel):
    """Публичные метаданные загруженного документа."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    status: Literal["uploaded", "processing", "ready", "failed"]
    page_count: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Страница списка документов."""

    model_config = ConfigDict(frozen=True)

    items: list[DocumentResponse]
    limit: int
    offset: int


class QuestionRequest(BaseModel):
    """Вопрос пользователя по одному документу."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    question: str = Field(min_length=1, max_length=2000)


class QuestionListResponse(BaseModel):
    """Последние ответы по документу."""

    model_config = ConfigDict(frozen=True)

    items: list[RagAnswer]
