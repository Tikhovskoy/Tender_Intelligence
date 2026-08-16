"""Зависимости HTTP-слоя."""

from fastapi import Request

from app.application.document_processing import DocumentProcessingService
from app.application.documents import DocumentService


def get_document_service(request: Request) -> DocumentService:
    """Вернуть настроенный сервис документов."""
    service = getattr(request.app.state, "document_service", None)
    if not isinstance(service, DocumentService):
        raise RuntimeError("Сервис документов не настроен")
    return service


def get_document_processor(request: Request) -> DocumentProcessingService | None:
    """Вернуть обработчик документов, если он настроен в приложении."""
    processor = getattr(request.app.state, "document_processor", None)
    return processor if isinstance(processor, DocumentProcessingService) else None
