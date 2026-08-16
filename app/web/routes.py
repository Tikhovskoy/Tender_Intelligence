"""HTML-маршруты на Jinja2 и HTMX."""

from datetime import datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.api.dependencies import (
    get_document_processor,
    get_document_service,
    get_rag_service,
    get_tender_analysis_service,
)
from app.application.document_processing import DocumentProcessingService
from app.application.documents import DocumentService
from app.application.rag import RagService
from app.application.tender_analysis import TenderAnalysisService
from app.domain.documents import DocumentStatus
from app.domain.exceptions import AnalysisNotFoundError, ApplicationError, FileTooLargeError
from app.domain.tender import TenderCard

TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=TEMPLATES_PATH)


def format_size(value: int) -> str:
    """Показать размер файла в понятном виде."""
    if value < 1024:
        return f"{value} Б"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} КБ"
    return f"{value / (1024 * 1024):.1f} МБ"


def format_datetime(value: datetime) -> str:
    """Показать локализованную дату без технических деталей."""
    return value.strftime("%d.%m.%Y · %H:%M")


def relevance_percent(value: float) -> int:
    """Преобразовать cosine similarity в процент для интерфейса."""
    return round(max(0.0, min(1.0, value)) * 100)


def format_page_count(value: int) -> str:
    """Согласовать число страниц с русским существительным."""
    remainder = value % 100
    if 11 <= remainder <= 14:
        word = "страниц"
    elif value % 10 == 1:
        word = "страница"
    elif value % 10 in {2, 3, 4}:
        word = "страницы"
    else:
        word = "страниц"
    return f"{value} {word}"


templates.env.filters["file_size"] = format_size
templates.env.filters["date_time"] = format_datetime
templates.env.filters["relevance_percent"] = relevance_percent
templates.env.filters["page_count"] = format_page_count

router = APIRouter(include_in_schema=False)

DocumentServiceDependency = Annotated[DocumentService, Depends(get_document_service)]
DocumentProcessorDependency = Annotated[
    DocumentProcessingService | None,
    Depends(get_document_processor),
]
AnalysisServiceDependency = Annotated[
    TenderAnalysisService,
    Depends(get_tender_analysis_service),
]
RagServiceDependency = Annotated[RagService, Depends(get_rag_service)]


def _context(request: Request, **values: Any) -> dict[str, Any]:
    return {"request": request, **values}


def _error_status(error: ApplicationError) -> int:
    return 413 if isinstance(error, FileTooLargeError) else 400


def _error_response(request: Request, error: ApplicationError) -> Response:
    """Вернуть ошибку, которую HTMX сможет вставить в целевой блок."""
    status_code = 200 if request.headers.get("HX-Request") == "true" else _error_status(error)
    return templates.TemplateResponse(
        request=request,
        name="partials/error.html",
        context=_context(request, error=error.message),
        status_code=status_code,
    )


async def _optional_analysis(
    service: TenderAnalysisService,
    document_id: UUID,
) -> TenderCard | None:
    try:
        return await service.get(document_id)
    except AnalysisNotFoundError:
        return None


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, service: DocumentServiceDependency) -> Response:
    """Показать загрузку и последние документы."""
    documents = await service.list(limit=50, offset=0)
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context=_context(request, documents=documents),
    )


@router.post("/documents", response_class=HTMLResponse)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File(description="PDF-документ")],
    service: DocumentServiceDependency,
    processor: DocumentProcessorDependency,
) -> Response:
    """Загрузить документ из HTML-формы и открыть его страницу."""
    try:
        document = await service.upload(
            file,
            filename=file.filename,
            content_type=file.content_type,
        )
    except ApplicationError as error:
        return _error_response(request, error)
    if processor is not None:
        background_tasks.add_task(processor.process, document.id)
    target = f"/documents/{document.id}"
    if request.headers.get("HX-Request") == "true":
        return HTMLResponse(headers={"HX-Redirect": target})
    return RedirectResponse(target, status_code=303)


@router.get("/documents/{document_id}", response_class=HTMLResponse)
async def document_page(
    request: Request,
    document_id: UUID,
    documents: DocumentServiceDependency,
    analyses: AnalysisServiceDependency,
    rag: RagServiceDependency,
) -> Response:
    """Показать состояние, карточку и историю вопросов документа."""
    document = await documents.get(document_id)
    analysis = await _optional_analysis(analyses, document_id)
    answers = await rag.list_answers(document_id, limit=50)
    return templates.TemplateResponse(
        request=request,
        name="document.html",
        context=_context(
            request,
            document=document,
            analysis=analysis,
            answers=answers,
        ),
    )


@router.get("/documents/{document_id}/status", response_class=HTMLResponse)
async def document_status(
    request: Request,
    document_id: UUID,
    service: DocumentServiceDependency,
) -> Response:
    """Обновить статус обработки без перезагрузки во время ожидания."""
    document = await service.get(document_id)
    response = templates.TemplateResponse(
        request=request,
        name="partials/status.html",
        context=_context(request, document=document),
    )
    if document.status in {DocumentStatus.READY, DocumentStatus.FAILED}:
        response.headers["HX-Refresh"] = "true"
    return response


@router.post("/documents/{document_id}/retry", response_class=HTMLResponse)
async def retry_document_processing(
    request: Request,
    document_id: UUID,
    background_tasks: BackgroundTasks,
    processor: DocumentProcessorDependency,
) -> Response:
    """Повторно запустить обработку и сразу показать ожидание."""
    if processor is None:
        return templates.TemplateResponse(
            request=request,
            name="partials/error.html",
            context=_context(request, error="Сервис обработки документов не настроен"),
        )
    try:
        document = await processor.prepare_retry(document_id)
    except ApplicationError as error:
        return _error_response(request, error)
    background_tasks.add_task(processor.process, document_id)
    return templates.TemplateResponse(
        request=request,
        name="partials/status.html",
        context=_context(request, document=document),
    )


@router.post("/documents/{document_id}/analysis", response_class=HTMLResponse)
async def analyze_document(
    request: Request,
    document_id: UUID,
    service: AnalysisServiceDependency,
) -> Response:
    """Сформировать карточку и вернуть HTML-фрагмент."""
    try:
        analysis = await service.analyze(document_id)
    except ApplicationError as error:
        return _error_response(request, error)
    return templates.TemplateResponse(
        request=request,
        name="partials/analysis.html",
        context=_context(request, analysis=analysis),
    )


@router.post("/documents/{document_id}/questions", response_class=HTMLResponse)
async def ask_question(
    request: Request,
    document_id: UUID,
    question: Annotated[str, Form(min_length=1, max_length=2000)],
    service: RagServiceDependency,
) -> Response:
    """Ответить на вопрос и вернуть элемент истории."""
    try:
        answer = await service.ask(document_id, question)
    except ApplicationError as error:
        return _error_response(request, error)
    return templates.TemplateResponse(
        request=request,
        name="partials/answer.html",
        context=_context(request, answer=answer),
    )
