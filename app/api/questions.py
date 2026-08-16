"""API вопросов и ответов по документу."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_rag_service
from app.api.schemas import ErrorResponse, QuestionListResponse, QuestionRequest
from app.application.rag import RagService
from app.domain.rag import RagAnswer

router = APIRouter(prefix="/api/v1/documents", tags=["Вопросы по документу"])

RagServiceDependency = Annotated[RagService, Depends(get_rag_service)]


@router.post(
    "/{document_id}/questions",
    response_model=RagAnswer,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_502_BAD_GATEWAY: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def ask_question(
    document_id: UUID,
    payload: QuestionRequest,
    service: RagServiceDependency,
) -> RagAnswer:
    """Ответить на вопрос только по содержимому документа."""
    return await service.ask(document_id, payload.question)


@router.get(
    "/{document_id}/questions",
    response_model=QuestionListResponse,
    responses={status.HTTP_404_NOT_FOUND: {"model": ErrorResponse}},
)
async def list_questions(
    document_id: UUID,
    service: RagServiceDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> QuestionListResponse:
    """Вернуть историю вопросов от новых к старым."""
    return QuestionListResponse(items=list(await service.list_answers(document_id, limit=limit)))
