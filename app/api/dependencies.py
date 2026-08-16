"""Зависимости HTTP-слоя."""

from fastapi import Request

from app.application.documents import DocumentService


def get_document_service(request: Request) -> DocumentService:
    """Вернуть настроенный сервис документов."""
    service = getattr(request.app.state, "document_service", None)
    if not isinstance(service, DocumentService):
        raise RuntimeError("Сервис документов не настроен")
    return service
