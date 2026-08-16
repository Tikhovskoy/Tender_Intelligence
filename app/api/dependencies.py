"""Зависимости HTTP-слоя."""

from fastapi import Request

from app.application.document_processing import DocumentProcessingService
from app.application.documents import DocumentService
from app.application.tender_analysis import TenderAnalysisService


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


def get_tender_analysis_service(request: Request) -> TenderAnalysisService:
    """Вернуть настроенный сценарий анализа тендера."""
    service = getattr(request.app.state, "tender_analysis_service", None)
    if not isinstance(service, TenderAnalysisService):
        raise RuntimeError("Сервис анализа тендера не настроен")
    return service
