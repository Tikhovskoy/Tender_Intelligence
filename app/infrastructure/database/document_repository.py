"""Репозиторий метаданных документов в PostgreSQL."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select

from app.domain.documents import DocumentRecord, DocumentStatus, ExtractedPage, StoredDocument
from app.infrastructure.database.connection import Database
from app.infrastructure.database.models import Document, DocumentPage


class SqlAlchemyDocumentRepository:
    """Реализация операций с документами через SQLAlchemy."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def create(self, document: StoredDocument) -> DocumentRecord:
        """Создать документ со статусом uploaded."""
        model = Document(
            original_filename=document.original_filename,
            stored_filename=document.stored_filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            sha256=document.sha256,
        )
        async with self.database.session() as session:
            session.add(model)
            await session.commit()
            await session.refresh(model)
        return self._to_record(model)

    async def get(self, document_id: UUID) -> DocumentRecord | None:
        """Найти документ по UUID."""
        async with self.database.session() as session:
            model = await session.get(Document, document_id)
        return self._to_record(model) if model is not None else None

    async def list(self, *, limit: int, offset: int) -> Sequence[DocumentRecord]:
        """Вернуть документы от новых к старым."""
        statement = (
            select(Document)
            .order_by(Document.created_at.desc(), Document.id.desc())
            .limit(limit)
            .offset(offset)
        )
        async with self.database.session() as session:
            result = await session.scalars(statement)
            models = result.all()
        return [self._to_record(model) for model in models]

    async def mark_processing(self, document_id: UUID) -> None:
        """Начать обработку и очистить результат предыдущей попытки."""
        async with self.database.session() as session:
            model = await session.get(Document, document_id)
            if model is None:
                raise RuntimeError("Документ для обработки не найден")
            await session.execute(
                delete(DocumentPage).where(DocumentPage.document_id == document_id)
            )
            model.status = DocumentStatus.PROCESSING
            model.page_count = None
            model.error_code = None
            model.error_message = None
            await session.commit()

    async def save_pages(self, document_id: UUID, pages: Sequence[ExtractedPage]) -> None:
        """Сохранить страницы и выставить итоговый статус ready."""
        async with self.database.session() as session:
            model = await session.get(Document, document_id)
            if model is None:
                raise RuntimeError("Документ для обработки не найден")
            session.add_all(
                DocumentPage(
                    document_id=document_id,
                    page_number=page.page_number,
                    text=page.text,
                )
                for page in pages
            )
            model.status = DocumentStatus.READY
            model.page_count = len(pages)
            model.error_code = None
            model.error_message = None
            await session.commit()

    async def mark_failed(self, document_id: UUID, *, code: str, message: str) -> None:
        """Сохранить ошибку обработки без технических деталей."""
        async with self.database.session() as session:
            model = await session.get(Document, document_id)
            if model is None:
                raise RuntimeError("Документ для обработки не найден")
            model.status = DocumentStatus.FAILED
            model.page_count = None
            model.error_code = code
            model.error_message = message
            await session.commit()

    @staticmethod
    def _to_record(model: Document) -> DocumentRecord:
        return DocumentRecord(
            id=model.id,
            original_filename=model.original_filename,
            stored_filename=model.stored_filename,
            content_type=model.content_type,
            size_bytes=model.size_bytes,
            sha256=model.sha256,
            status=model.status,
            page_count=model.page_count,
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
