"""Семантический поиск по одному документу."""

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
        return await self.documents.search_similar(
            document_id,
            query_embedding,
            embedding_model=self.provider.model,
            limit=self.top_k,
        )
