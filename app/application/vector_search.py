"""Семантический поиск по одному документу."""

import re
from collections.abc import Sequence
from uuid import UUID

from app.domain.documents import (
    DocumentRepository,
    DocumentStatus,
    EmbeddingProvider,
    VectorSearchResult,
)
from app.domain.exceptions import (
    ApplicationError,
    DocumentNotFoundError,
    DocumentNotReadyError,
    ProviderUnavailableError,
)


class VectorSearchService:
    """Построение вектора вопроса и изолированный top-k поиск."""

    def __init__(
        self,
        documents: DocumentRepository,
        provider: EmbeddingProvider | None,
        *,
        top_k: int,
    ) -> None:
        self.documents = documents
        self.provider = provider
        self.top_k = top_k

    _WORD_PATTERN = re.compile(r"[а-яёa-z0-9]+", re.IGNORECASE)
    _STOP_WORDS = frozenset(
        {
            "как",
            "какие",
            "какой",
            "какова",
            "что",
            "это",
            "для",
            "или",
            "при",
            "есть",
            "ли",
        }
    )
    _CONTRACTOR_TERMS = frozenset(
        {
            "исполнитель",
            "исполнителя",
            "исполнителю",
            "подрядчик",
            "подрядчика",
            "подрядчику",
        }
    )
    _CONTRACTOR_SYNONYMS = frozenset(
        {
            "участник",
            "участника",
            "участникам",
            "поставщик",
            "поставщика",
            "поставщику",
        }
    )

    async def search(self, document_id: UUID, question: str) -> Sequence[VectorSearchResult]:
        normalized_question = question.strip()
        if not normalized_question:
            raise ApplicationError("Вопрос не может быть пустым", code="question_empty")
        document = await self.documents.get(document_id)
        if document is None:
            raise DocumentNotFoundError("Документ не найден", code="document_not_found")
        if document.status != DocumentStatus.READY:
            raise DocumentNotReadyError(
                "Документ ещё не готов к поиску",
                code="document_not_ready",
            )
        if self.provider is None:
            raise ProviderUnavailableError(
                "Провайдер embeddings не настроен",
                code="embedding_provider_not_configured",
            )
        query_embedding = await self.provider.embed_query(normalized_question)
        lexical_query = " OR ".join(sorted(self._expanded_terms(normalized_question)))
        candidates = await self.documents.search_similar(
            document_id,
            query_embedding,
            query_text=lexical_query,
            embedding_model=self.provider.model,
            limit=max(20, self.top_k),
        )
        return self._rerank(normalized_question, candidates)[: self.top_k]

    @classmethod
    def _rerank(
        cls,
        question: str,
        candidates: Sequence[VectorSearchResult],
    ) -> list[VectorSearchResult]:
        """Дополнить семантическую оценку точным совпадением терминов."""
        query_terms = cls._expanded_terms(question)

        def score(item: VectorSearchResult) -> tuple[float, float, int]:
            text_terms = cls._terms(item.text)
            lexical_share = len(query_terms & text_terms) / max(1, len(query_terms))
            combined = item.relevance + min(0.3, lexical_share * 0.5)
            return combined, item.relevance, -item.chunk_index

        return sorted(candidates, key=score, reverse=True)

    @classmethod
    def _terms(cls, value: str) -> set[str]:
        return {
            word
            for word in cls._WORD_PATTERN.findall(value.casefold())
            if len(word) >= 3 and word not in cls._STOP_WORDS
        }

    @classmethod
    def _expanded_terms(cls, question: str) -> set[str]:
        terms = cls._terms(question)
        if terms & cls._CONTRACTOR_TERMS:
            terms |= cls._CONTRACTOR_TERMS | cls._CONTRACTOR_SYNONYMS
        return terms
