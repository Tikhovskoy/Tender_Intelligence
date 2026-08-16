"""Сценарии загрузки и просмотра документов."""

from collections.abc import Sequence
from pathlib import PurePosixPath
from uuid import UUID

from app.domain.documents import (
    AsyncFileReader,
    DocumentRecord,
    DocumentRepository,
    DocumentStorage,
)
from app.domain.exceptions import DocumentNotFoundError, InvalidDocumentError

PDF_CONTENT_TYPES = frozenset({"application/pdf", "application/x-pdf"})


class DocumentService:
    """Операции с загруженными документами."""

    def __init__(
        self,
        repository: DocumentRepository,
        storage: DocumentStorage,
        *,
        max_size_bytes: int,
        chunk_size_bytes: int,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.max_size_bytes = max_size_bytes
        self.chunk_size_bytes = chunk_size_bytes

    async def upload(
        self,
        source: AsyncFileReader,
        *,
        filename: str | None,
        content_type: str | None,
    ) -> DocumentRecord:
        """Проверить файл, сохранить его и создать запись в БД."""
        normalized_filename = self._validate_filename(filename)
        normalized_content_type = self._validate_content_type(content_type)
        stored_document = await self.storage.save_pdf(
            source,
            original_filename=normalized_filename,
            content_type=normalized_content_type,
            max_size_bytes=self.max_size_bytes,
            chunk_size_bytes=self.chunk_size_bytes,
        )
        try:
            return await self.repository.create(stored_document)
        except Exception:
            await self.storage.delete(stored_document.stored_filename)
            raise

    async def get(self, document_id: UUID) -> DocumentRecord:
        """Вернуть документ или понятную ошибку."""
        document = await self.repository.get(document_id)
        if document is None:
            raise DocumentNotFoundError(
                "Документ не найден",
                code="document_not_found",
            )
        return document

    async def list(self, *, limit: int, offset: int) -> Sequence[DocumentRecord]:
        """Вернуть страницу списка документов."""
        return await self.repository.list(limit=limit, offset=offset)

    @staticmethod
    def _validate_filename(filename: str | None) -> str:
        if not filename:
            raise InvalidDocumentError("Не указано имя файла", code="filename_missing")
        normalized = PurePosixPath(filename.replace("\\", "/")).name.strip()
        if not normalized or len(normalized) > 255 or "\x00" in normalized:
            raise InvalidDocumentError("Некорректное имя файла", code="filename_invalid")
        if not normalized.lower().endswith(".pdf"):
            raise InvalidDocumentError(
                "Допускаются только файлы PDF",
                code="file_extension_invalid",
            )
        return normalized

    @staticmethod
    def _validate_content_type(content_type: str | None) -> str:
        normalized = (content_type or "").lower().strip()
        if normalized not in PDF_CONTENT_TYPES:
            raise InvalidDocumentError(
                "Недопустимый тип файла. Требуется PDF",
                code="content_type_invalid",
            )
        return normalized
