"""Основные типы документов."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
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
    stored_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    status: DocumentStatus
    page_count: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    """Текст, извлечённый из одной страницы PDF."""

    page_number: int
    text: str


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

    def resolve_path(self, stored_filename: str) -> Path:
        """Вернуть безопасный путь к сохранённому документу."""
        ...


class DocumentTextExtractor(Protocol):
    """Извлечение постраничного текста из документа."""

    async def extract(self, path: Path) -> Sequence[ExtractedPage]:
        """Извлечь текст и сохранить исходную нумерацию страниц."""
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

    async def mark_processing(self, document_id: UUID) -> None:
        """Отметить начало обработки документа."""
        ...

    async def save_pages(self, document_id: UUID, pages: Sequence[ExtractedPage]) -> None:
        """Сохранить страницы и завершить обработку документа."""
        ...

    async def mark_failed(self, document_id: UUID, *, code: str, message: str) -> None:
        """Сохранить понятную причину ошибки обработки."""
        ...
