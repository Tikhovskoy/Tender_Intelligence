"""API структурированной карточки тендера."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_tender_analysis_service
from app.api.schemas import ErrorResponse
from app.application.tender_analysis import TenderAnalysisService
from app.domain.tender import TenderCard

router = APIRouter(prefix="/api/v1/documents", tags=["Карточка тендера"])

AnalysisServiceDependency = Annotated[
    TenderAnalysisService,
    Depends(get_tender_analysis_service),
]


@router.post(
    "/{document_id}/analysis",
    response_model=TenderCard,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_502_BAD_GATEWAY: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def analyze_tender(
    document_id: UUID,
    service: AnalysisServiceDependency,
) -> TenderCard:
    """Сформировать или обновить карточку тендера."""
    return await service.analyze(document_id)


@router.get(
    "/{document_id}/analysis",
    response_model=TenderCard,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def get_tender_analysis(
    document_id: UUID,
    service: AnalysisServiceDependency,
) -> TenderCard:
    """Вернуть ранее сформированную карточку."""
    return await service.get(document_id)
