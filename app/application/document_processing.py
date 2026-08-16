"""Сценарий извлечения текста из загруженного документа."""

from dataclasses import replace
from uuid import UUID

import structlog

from app.domain.documents import (
    DocumentChunker,
    DocumentRecord,
    DocumentRepository,
    DocumentStatus,
    DocumentStorage,
    DocumentTextExtractor,
    EmbeddingProvider,
)
from app.domain.exceptions import ApplicationError, DocumentNotFoundError

logger = structlog.get_logger(__name__)


class DocumentProcessingService:
    """Управление статусами и сохранением постраничного текста."""

    def __init__(
        self,
        repository: DocumentRepository,
        storage: DocumentStorage,
        extractor: DocumentTextExtractor,
        chunker: DocumentChunker,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.extractor = extractor
        self.chunker = chunker
        self.embedding_provider = embedding_provider

    async def process(self, document_id: UUID) -> None:
        """Извлечь текст, не допуская падения фонового сценария."""
        document = await self.repository.get(document_id)
        if document is None:
            await logger.awarning("document_processing_skipped", document_id=str(document_id))
            return

        if document.status != DocumentStatus.PROCESSING:
            await self.repository.mark_processing(document_id)
        try:
            path = self.storage.resolve_path(document.stored_filename)
            pages = await self.extractor.extract(path)
            chunks = list(self.chunker.split(pages))
            if self.embedding_provider is not None and chunks:
                vectors = await self.embedding_provider.embed_documents(
                    [chunk.text for chunk in chunks]
                )
                if len(vectors) != len(chunks):
                    raise RuntimeError("Провайдер вернул неверное количество векторов")
                chunks = [
                    replace(
                        chunk,
                        embedding=list(vector),
                        embedding_model=self.embedding_provider.model,
                    )
                    for chunk, vector in zip(chunks, vectors, strict=True)
                ]
            await self.repository.save_content(document_id, pages, chunks)
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
                chunk_count=len(chunks),
            )

    async def prepare_retry(self, document_id: UUID) -> DocumentRecord:
        """Перевести ошибочный документ в обработку перед фоновым запуском."""
        document = await self.repository.get(document_id)
        if document is None:
            raise DocumentNotFoundError(
                "Документ не найден",
                code="document_not_found",
            )
        if document.status != DocumentStatus.FAILED:
            raise ApplicationError(
                "Повторная обработка доступна только после ошибки",
                code="document_retry_not_allowed",
            )
        await self.repository.mark_processing(document_id)
        prepared = await self.repository.get(document_id)
        if prepared is None:
            raise DocumentNotFoundError(
                "Документ не найден",
                code="document_not_found",
            )
        return prepared
