"""Сценарий извлечения текста из загруженного документа."""

from uuid import UUID

import structlog

from app.domain.documents import DocumentRepository, DocumentStorage, DocumentTextExtractor
from app.domain.exceptions import ApplicationError

logger = structlog.get_logger(__name__)


class DocumentProcessingService:
    """Управление статусами и сохранением постраничного текста."""

    def __init__(
        self,
        repository: DocumentRepository,
        storage: DocumentStorage,
        extractor: DocumentTextExtractor,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.extractor = extractor

    async def process(self, document_id: UUID) -> None:
        """Извлечь текст, не допуская падения фонового сценария."""
        document = await self.repository.get(document_id)
        if document is None:
            await logger.awarning("document_processing_skipped", document_id=str(document_id))
            return

        await self.repository.mark_processing(document_id)
        try:
            path = self.storage.resolve_path(document.stored_filename)
            pages = await self.extractor.extract(path)
            await self.repository.save_pages(document_id, pages)
        except ApplicationError as error:
            await self.repository.mark_failed(
                document_id,
                code=error.code,
                message=error.message,
            )
            await logger.awarning(
                "document_processing_failed",
                document_id=str(document_id),
                error_code=error.code,
            )
        except Exception:
            await self.repository.mark_failed(
                document_id,
                code="document_processing_failed",
                message="Не удалось обработать PDF",
            )
            await logger.aexception(
                "document_processing_failed",
                document_id=str(document_id),
                error_code="document_processing_failed",
            )
        else:
            await logger.ainfo(
                "document_processing_completed",
                document_id=str(document_id),
                page_count=len(pages),
            )
