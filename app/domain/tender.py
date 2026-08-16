"""Структурированная карточка тендера и контекст анализа."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

NOT_FOUND = "не найдено в документе"


class SourceCitation(BaseModel):
    """Короткая точная цитата с номером страницы."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    page_number: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=500)


class SourcedText(BaseModel):
    """Текстовое значение и подтверждающие источники."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str = Field(min_length=1)
    sources: list[SourceCitation]

    @model_validator(mode="after")
    def validate_sources(self) -> "SourcedText":
        if self.value == NOT_FOUND and self.sources:
            raise ValueError("Для отсутствующего значения источники не допускаются")
        if self.value != NOT_FOUND and not self.sources:
            raise ValueError("Для найденного значения требуется источник")
        return self


class SourcedList(BaseModel):
    """Список значений и подтверждающие источники."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[str] = Field(min_length=1)
    sources: list[SourceCitation]

    @model_validator(mode="after")
    def validate_sources(self) -> "SourcedList":
        missing = self.items == [NOT_FOUND]
        if NOT_FOUND in self.items and not missing:
            raise ValueError("Признак отсутствия нельзя смешивать с найденными значениями")
        if missing and self.sources:
            raise ValueError("Для отсутствующего списка источники не допускаются")
        if not missing and not self.sources:
            raise ValueError("Для найденного списка требуется источник")
        return self


class TenderCard(BaseModel):
    """Строгий результат анализа тендерной документации."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    procurement_name: SourcedText
    customer: SourcedText
    contract_amount: SourcedText
    currency: SourcedText
    execution_period: SourcedText
    contractor_requirements: SourcedList
    penalties: SourcedList
    summary: SourcedText


@dataclass(frozen=True, slots=True)
class AnalysisChunk:
    """Фрагмент документа, доступный для анализа."""

    chunk_index: int
    page_number: int
    text: str


class TenderAnalysisProvider(Protocol):
    """Провайдер структурированного анализа."""

    name: str
    model: str

    async def analyze(self, chunks: Sequence[AnalysisChunk]) -> TenderCard:
        """Сформировать карточку строго по переданным фрагментам."""
        ...


class TenderAnalysisRepository(Protocol):
    """Хранилище результатов анализа."""

    async def get(self, document_id: UUID) -> TenderCard | None:
        """Получить сохранённую карточку."""
        ...

    async def save(
        self,
        document_id: UUID,
        card: TenderCard,
        *,
        provider: str,
        model: str,
        prompt_version: str,
    ) -> TenderCard:
        """Создать или заменить карточку документа."""
        ...
