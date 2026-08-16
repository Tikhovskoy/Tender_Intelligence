"""Формирование и сохранение ответов по найденному контексту."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.domain.documents import DocumentRepository, DocumentStatus, VectorSearchResult
from app.domain.exceptions import (
    ApplicationError,
    DocumentNotFoundError,
    DocumentNotReadyError,
    ProviderUnavailableError,
)
from app.domain.rag import (
    ANSWER_NOT_FOUND,
    GroundedAnswerDraft,
    QuestionAnswerProvider,
    QuestionRepository,
    RagAnswer,
    RagSource,
    VectorSearcher,
)


class RagService:
    """Ответы на вопросы исключительно по контексту одного документа."""

    def __init__(
        self,
        documents: DocumentRepository,
        searcher: VectorSearcher,
        questions: QuestionRepository,
        provider: QuestionAnswerProvider | None,
        *,
        min_relevance: float,
    ) -> None:
        self.documents = documents
        self.searcher = searcher
        self.questions = questions
        self.provider = provider
        self.min_relevance = min_relevance

    async def ask(self, document_id: UUID, question: str) -> RagAnswer:
        normalized_question = question.strip()
        if not normalized_question:
            raise ApplicationError("Вопрос не может быть пустым", code="question_empty")
        if len(normalized_question) > 2000:
            raise ApplicationError("Вопрос слишком длинный", code="question_too_long")
        document = await self.documents.get(document_id)
        if document is None:
            raise DocumentNotFoundError("Документ не найден", code="document_not_found")
        if document.status != DocumentStatus.READY:
            raise DocumentNotReadyError(
                "Документ ещё не готов к вопросам",
                code="document_not_ready",
            )
        if self.provider is None:
            raise ProviderUnavailableError(
                "Провайдер ответов не настроен",
                code="answer_provider_not_configured",
            )

        candidates = [
            item
            for item in await self.searcher.search(document_id, normalized_question)
            if item.relevance >= self.min_relevance
        ][:5]
        sources = self._build_sources(candidates)
        if len(sources) < 2:
            draft = GroundedAnswerDraft(
                answer=ANSWER_NOT_FOUND,
                context_sufficient=False,
            )
        else:
            draft = await self.provider.answer_question(normalized_question, candidates)

        return await self.questions.save(
            document_id,
            normalized_question,
            draft,
            sources,
            provider=self.provider.name,
            model=self.provider.model,
        )

    async def list_answers(self, document_id: UUID, *, limit: int) -> Sequence[RagAnswer]:
        if await self.documents.get(document_id) is None:
            raise DocumentNotFoundError("Документ не найден", code="document_not_found")
        return await self.questions.list(document_id, limit=limit)

    @staticmethod
    def _build_sources(candidates: Sequence[VectorSearchResult]) -> list[RagSource]:
        candidates_with_text = [item for item in candidates if item.text.strip()]
        return [
            RagSource(
                chunk_id=item.id,
                page_number=item.page_number,
                quote=item.text.strip()[:700],
                relevance=item.relevance,
                position=position,
            )
            for position, item in enumerate(candidates_with_text, start=1)
        ]
