"""Основные типы документов."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class DocumentStatus(StrEnum):
    """Этап обработки загруженного документа."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class StoredDocument:
    """Результат безопасного сохранения исходного файла."""

    original_filename: str
    stored_filename: str
    content_type: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    """Данные документа, доступные прикладному слою."""

    id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    status: DocumentStatus
    page_count: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class AsyncFileReader(Protocol):
    """Асинхронный источник содержимого файла."""

    async def read(self, size: int = -1) -> bytes:
        """Прочитать следующую часть содержимого."""
        ...


class DocumentStorage(Protocol):
    """Хранилище исходных документов."""

    async def save_pdf(
        self,
        source: AsyncFileReader,
        *,
        original_filename: str,
        content_type: str,
        max_size_bytes: int,
        chunk_size_bytes: int,
    ) -> StoredDocument:
        """Проверить и сохранить PDF."""
        ...

    async def delete(self, stored_filename: str) -> None:
        """Удалить сохранённый файл при откате операции."""
        ...


class DocumentRepository(Protocol):
    """Хранилище метаданных документов."""

    async def create(self, document: StoredDocument) -> DocumentRecord:
        """Создать запись документа."""
        ...

    async def get(self, document_id: UUID) -> DocumentRecord | None:
        """Найти документ по идентификатору."""
        ...

    async def list(self, *, limit: int, offset: int) -> Sequence[DocumentRecord]:
        """Вернуть документы от новых к старым."""
        ...
