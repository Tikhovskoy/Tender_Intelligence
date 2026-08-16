from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.documents import DocumentRecord, DocumentStatus, StoredDocument


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

    async def create(self, document: StoredDocument) -> DocumentRecord:
        now = datetime.now(UTC)
        record = DocumentRecord(
            id=uuid4(),
            original_filename=document.original_filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
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
