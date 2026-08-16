"""API загрузки и просмотра документов."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile, status

from app.api.dependencies import get_document_processor, get_document_service
from app.api.schemas import DocumentListResponse, DocumentResponse, ErrorResponse
from app.application.document_processing import DocumentProcessingService
from app.application.documents import DocumentService

router = APIRouter(prefix="/api/v1/documents", tags=["Документы"])

DocumentServiceDependency = Annotated[DocumentService, Depends(get_document_service)]
DocumentProcessorDependency = Annotated[
    DocumentProcessingService | None,
    Depends(get_document_processor),
]


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_413_CONTENT_TOO_LARGE: {"model": ErrorResponse},
    },
)
async def upload_document(
    file: Annotated[UploadFile, File(description="PDF-документ")],
    service: DocumentServiceDependency,
    processor: DocumentProcessorDependency,
    background_tasks: BackgroundTasks,
) -> DocumentResponse:
    """Загрузить PDF и зарегистрировать его для обработки."""
    record = await service.upload(
        file,
        filename=file.filename,
        content_type=file.content_type,
    )
    if processor is not None:
        background_tasks.add_task(processor.process, record.id)
    return DocumentResponse.model_validate(record)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    service: DocumentServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    """Вернуть список ранее загруженных документов."""
    records = await service.list(limit=limit, offset=offset)
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(record) for record in records],
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{document_id}/retry",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def retry_document_processing(
    document_id: UUID,
    processor: DocumentProcessorDependency,
    background_tasks: BackgroundTasks,
) -> DocumentResponse:
    """Повторно запустить обработку документа после ошибки."""
    if processor is None:
        raise RuntimeError("Сервис обработки документов не настроен")
    record = await processor.prepare_retry(document_id)
    background_tasks.add_task(processor.process, document_id)
    return DocumentResponse.model_validate(record)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def get_document(
    document_id: UUID,
    service: DocumentServiceDependency,
) -> DocumentResponse:
    """Вернуть сведения об одном документе."""
    record = await service.get(document_id)
    return DocumentResponse.model_validate(record)
