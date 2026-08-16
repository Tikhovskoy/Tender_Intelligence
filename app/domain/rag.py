"""Типы вопросов, ответов и подтверждающих источников."""

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.documents import VectorSearchResult

ANSWER_NOT_FOUND = "Ответ не найден в документе."


class GroundedAnswerDraft(BaseModel):
    """Структурированный ответ провайдера без доверенных источников."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: str = Field(min_length=1)
    context_sufficient: bool

    @model_validator(mode="after")
    def normalize_insufficient_answer(self) -> "GroundedAnswerDraft":
        if not self.context_sufficient and self.answer != ANSWER_NOT_FOUND:
            raise ValueError("При недостаточном контексте требуется стандартный ответ")
        if self.context_sufficient and self.answer == ANSWER_NOT_FOUND:
            raise ValueError("Подтверждённый ответ не может быть пустым")
        return self


class RagSource(BaseModel):
    """Источник ответа, сформированный из найденного чанка."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: UUID
    page_number: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=700)
    relevance: float = Field(ge=-1, le=1)
    position: int = Field(ge=1, le=5)


class RagAnswer(BaseModel):
    """Сохранённый ответ на вопрос по документу."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    document_id: UUID
    question: str
    answer: str
    context_sufficient: bool
    sources: list[RagSource] = Field(max_length=5)
    created_at: datetime

    @model_validator(mode="after")
    def validate_source_count(self) -> "RagAnswer":
        if self.context_sufficient and len(self.sources) < 2:
            raise ValueError("Подтверждённый ответ должен содержать не менее двух источников")
        return self


class QuestionAnswerProvider(Protocol):
    """Провайдер ответа только по найденному контексту."""

    name: str
    model: str

    async def answer_question(
        self,
        question: str,
        chunks: Sequence[VectorSearchResult],
    ) -> GroundedAnswerDraft:
        """Ответить по переданным фрагментам или признать нехватку данных."""
        ...


class QuestionRepository(Protocol):
    """Хранилище вопросов, ответов и источников."""

    async def save(
        self,
        document_id: UUID,
        question: str,
        draft: GroundedAnswerDraft,
        sources: Sequence[RagSource],
        *,
        provider: str,
        model: str,
    ) -> RagAnswer:
        """Сохранить ответ и его источники одной транзакцией."""
        ...

    async def list(self, document_id: UUID, *, limit: int) -> Sequence[RagAnswer]:
        """Вернуть последние ответы по документу."""
        ...


class VectorSearcher(Protocol):
    """Поиск релевантных фрагментов документа."""

    async def search(
        self,
        document_id: UUID,
        question: str,
    ) -> Sequence[VectorSearchResult]:
        """Найти top-k фрагментов для вопроса."""
        ...
