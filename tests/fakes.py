from collections.abc import Sequence
from datetime import UTC, datetime
from math import sqrt
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from app.domain.documents import (
    DocumentRecord,
    DocumentStatus,
    ExtractedPage,
    StoredDocument,
    TextChunk,
    VectorSearchResult,
)
from app.domain.rag import GroundedAnswerDraft, RagAnswer, RagSource
from app.domain.tender import AnalysisChunk, TenderCard


class FakeDatabase:
    """Управляемая заглушка подключения к БД."""

    def __init__(self, *, ready: bool = True) -> None:
        self.ready = ready
        self.connected = False

    async def connect(self) -> bool:
        self.connected = True
        return self.ready

    async def is_ready(self) -> bool:
        return self.connected and self.ready

    async def disconnect(self) -> None:
        self.connected = False


class InMemoryDocumentRepository:
    """Репозиторий документов без внешней БД."""

    def __init__(self) -> None:
        self.records: list[DocumentRecord] = []
        self.pages: dict[UUID, list[ExtractedPage]] = {}
        self.chunks: dict[UUID, list[TextChunk]] = {}

    async def create(self, document: StoredDocument) -> DocumentRecord:
        now = datetime.now(UTC)
        record = DocumentRecord(
            id=uuid4(),
            original_filename=document.original_filename,
            stored_filename=document.stored_filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            sha256=document.sha256,
            status=DocumentStatus.UPLOADED,
            page_count=None,
            error_message=None,
            created_at=now,
            updated_at=now,
        )
        self.records.insert(0, record)
        return record

    async def get(self, document_id: UUID) -> DocumentRecord | None:
        return next((record for record in self.records if record.id == document_id), None)

    async def list(self, *, limit: int, offset: int) -> Sequence[DocumentRecord]:
        return self.records[offset : offset + limit]

    async def mark_processing(self, document_id: UUID) -> None:
        self._replace(document_id, status=DocumentStatus.PROCESSING)
        self.pages.pop(document_id, None)
        self.chunks.pop(document_id, None)

    async def save_content(
        self,
        document_id: UUID,
        pages: Sequence[ExtractedPage],
        chunks: Sequence[TextChunk],
    ) -> None:
        self.pages[document_id] = list(pages)
        self.chunks[document_id] = list(chunks)
        self._replace(
            document_id,
            status=DocumentStatus.READY,
            page_count=len(pages),
            error_message=None,
        )

    async def mark_failed(self, document_id: UUID, *, code: str, message: str) -> None:
        self._replace(
            document_id,
            status=DocumentStatus.FAILED,
            page_count=None,
            error_message=message,
        )

    async def list_analysis_chunks(self, document_id: UUID) -> Sequence[AnalysisChunk]:
        return [
            AnalysisChunk(
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                text=chunk.text,
            )
            for chunk in self.chunks.get(document_id, [])
        ]

    async def search_similar(
        self,
        document_id: UUID,
        query_embedding: Sequence[float],
        *,
        embedding_model: str,
        limit: int,
    ) -> Sequence[VectorSearchResult]:
        results: list[VectorSearchResult] = []
        for chunk in self.chunks.get(document_id, []):
            if chunk.embedding is None or chunk.embedding_model != embedding_model:
                continue
            denominator = sqrt(sum(value * value for value in chunk.embedding)) * sqrt(
                sum(value * value for value in query_embedding)
            )
            relevance = (
                sum(
                    left * right
                    for left, right in zip(chunk.embedding, query_embedding, strict=True)
                )
                / denominator
                if denominator
                else 0.0
            )
            results.append(
                VectorSearchResult(
                    id=uuid5(NAMESPACE_URL, f"{document_id}:{chunk.chunk_index}"),
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    text=chunk.text,
                    relevance=relevance,
                )
            )
        return sorted(results, key=lambda item: item.relevance, reverse=True)[:limit]

    def _replace(
        self,
        document_id: UUID,
        *,
        status: DocumentStatus,
        page_count: int | None = None,
        error_message: str | None = None,
    ) -> None:
        for index, record in enumerate(self.records):
            if record.id == document_id:
                self.records[index] = DocumentRecord(
                    id=record.id,
                    original_filename=record.original_filename,
                    stored_filename=record.stored_filename,
                    content_type=record.content_type,
                    size_bytes=record.size_bytes,
                    sha256=record.sha256,
                    status=status,
                    page_count=page_count,
                    error_message=error_message,
                    created_at=record.created_at,
                    updated_at=datetime.now(UTC),
                )
                return
        raise RuntimeError("Документ для обработки не найден")


class InMemoryTenderAnalysisRepository:
    """Хранилище карточек без внешней БД."""

    def __init__(self) -> None:
        self.cards: dict[UUID, TenderCard] = {}
        self.saved_metadata: tuple[str, str, str] | None = None

    async def get(self, document_id: UUID) -> TenderCard | None:
        return self.cards.get(document_id)

    async def save(
        self,
        document_id: UUID,
        card: TenderCard,
        *,
        provider: str,
        model: str,
        prompt_version: str,
    ) -> TenderCard:
        self.cards[document_id] = card
        self.saved_metadata = (provider, model, prompt_version)
        return card


class InMemoryQuestionRepository:
    """История вопросов без внешней БД."""

    def __init__(self) -> None:
        self.answers: list[RagAnswer] = []
        self.saved_metadata: tuple[str, str] | None = None

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
        answer = RagAnswer(
            id=uuid4(),
            document_id=document_id,
            question=question,
            answer=draft.answer,
            context_sufficient=draft.context_sufficient,
            sources=list(sources),
            created_at=datetime.now(UTC),
        )
        self.answers.insert(0, answer)
        self.saved_metadata = (provider, model)
        return answer

    async def list(self, document_id: UUID, *, limit: int) -> Sequence[RagAnswer]:
        return [answer for answer in self.answers if answer.document_id == document_id][:limit]
