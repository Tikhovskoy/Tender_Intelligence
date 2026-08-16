"""Отбор контекста и формирование карточки тендера."""

import re
from collections.abc import Iterable, Sequence
from uuid import UUID

from app.domain.documents import DocumentRepository, DocumentStatus
from app.domain.exceptions import (
    AnalysisNotFoundError,
    DocumentNotFoundError,
    DocumentNotReadyError,
    InvalidProviderResponseError,
    ProviderUnavailableError,
)
from app.domain.tender import (
    AnalysisChunk,
    SourceCitation,
    TenderAnalysisProvider,
    TenderAnalysisRepository,
    TenderCard,
)

PROMPT_VERSION = "2"


class RelevantChunkSelector:
    """Эвристический отбор фрагментов с покрытием ключевых полей."""

    _KEYWORD_GROUPS = (
        ("закупк", "предмет", "наименование", "tender", "procurement"),
        ("заказчик", "организатор", "customer", "client"),
        ("цена", "стоимост", "сумм", "руб", "₽", "price", "amount"),
        ("срок", "период", "дней", "дата", "deadline", "period"),
        ("требован", "исполнител", "участник", "опыт", "лиценз", "requirement"),
        ("штраф", "пен", "неустой", "санкц", "ответствен", "penalty"),
    )

    def __init__(self, *, max_chunks: int, max_chars: int) -> None:
        if max_chunks <= 0 or max_chars <= 0:
            raise ValueError("Ограничения контекста должны быть положительными")
        self.max_chunks = max_chunks
        self.max_chars = max_chars

    def select(self, chunks: Sequence[AnalysisChunk]) -> Sequence[AnalysisChunk]:
        if not chunks:
            return []
        selected: set[int] = {0}
        lowered = [chunk.text.casefold() for chunk in chunks]
        for keywords in self._KEYWORD_GROUPS:
            best = max(
                range(len(chunks)),
                key=lambda index: self._score(lowered[index], keywords),
            )
            if self._score(lowered[best], keywords) > 0:
                selected.add(best)

        ranked = sorted(
            range(len(chunks)),
            key=lambda index: (
                -sum(self._score(lowered[index], group) for group in self._KEYWORD_GROUPS),
                chunks[index].chunk_index,
            ),
        )
        selected.update(ranked[: self.max_chunks])

        result: list[AnalysisChunk] = []
        used_chars = 0
        for index in sorted(selected, key=lambda item: chunks[item].chunk_index):
            if len(result) >= self.max_chunks:
                break
            chunk = chunks[index]
            remaining = self.max_chars - used_chars
            if remaining <= 0:
                break
            if len(chunk.text) > remaining:
                if result:
                    continue
                chunk = AnalysisChunk(
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    text=chunk.text[:remaining],
                )
            result.append(chunk)
            used_chars += len(chunk.text)
        return result

    @staticmethod
    def _score(text: str, keywords: Iterable[str]) -> int:
        return sum(text.count(keyword) for keyword in keywords)


class TenderAnalysisService:
    """Сценарий анализа только по отобранному контексту документа."""

    def __init__(
        self,
        documents: DocumentRepository,
        analyses: TenderAnalysisRepository,
        provider: TenderAnalysisProvider | None,
        selector: RelevantChunkSelector,
    ) -> None:
        self.documents = documents
        self.analyses = analyses
        self.provider = provider
        self.selector = selector

    async def analyze(self, document_id: UUID) -> TenderCard:
        document = await self.documents.get(document_id)
        if document is None:
            raise DocumentNotFoundError("Документ не найден", code="document_not_found")
        if document.status != DocumentStatus.READY:
            raise DocumentNotReadyError(
                "Документ ещё не готов к анализу",
                code="document_not_ready",
            )
        chunks = self.selector.select(await self.documents.list_analysis_chunks(document_id))
        if not chunks:
            raise DocumentNotReadyError(
                "В документе нет подготовленных фрагментов",
                code="document_chunks_missing",
            )
        if self.provider is None:
            raise ProviderUnavailableError(
                "Провайдер анализа не настроен",
                code="analysis_provider_not_configured",
            )
        card = await self.provider.analyze(chunks)
        self._validate_citations(card, chunks)
        return await self.analyses.save(
            document_id,
            card,
            provider=self.provider.name,
            model=self.provider.model,
            prompt_version=PROMPT_VERSION,
        )

    async def get(self, document_id: UUID) -> TenderCard:
        if await self.documents.get(document_id) is None:
            raise DocumentNotFoundError("Документ не найден", code="document_not_found")
        card = await self.analyses.get(document_id)
        if card is None:
            raise AnalysisNotFoundError(
                "Карточка тендера ещё не сформирована",
                code="analysis_not_found",
            )
        return card

    @classmethod
    def _validate_citations(
        cls,
        card: TenderCard,
        chunks: Sequence[AnalysisChunk],
    ) -> None:
        sources = cls._all_sources(card)
        page_context = {
            page: cls._normalize(
                " ".join(chunk.text for chunk in chunks if chunk.page_number == page)
            )
            for page in {chunk.page_number for chunk in chunks}
        }
        for source in sources:
            context = page_context.get(source.page_number, "")
            if cls._normalize(source.quote) not in context:
                raise InvalidProviderResponseError(
                    "Провайдер вернул источник, отсутствующий в документе",
                    code="invalid_analysis_source",
                )

    @staticmethod
    def _all_sources(card: TenderCard) -> list[SourceCitation]:
        return [
            source
            for field in (
                card.procurement_name,
                card.customer,
                card.contract_amount,
                card.currency,
                card.execution_period,
                card.contractor_requirements,
                card.penalties,
                card.summary,
            )
            for source in field.sources
        ]

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold()
