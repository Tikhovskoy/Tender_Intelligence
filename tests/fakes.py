from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.documents import (
    DocumentRecord,
    DocumentStatus,
    ExtractedPage,
    StoredDocument,
    TextChunk,
)


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
