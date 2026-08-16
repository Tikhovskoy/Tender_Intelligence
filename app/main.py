"""Точка сборки FastAPI-приложения."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app import __version__
from app.api.error_handlers import (
    application_error_handler,
    unexpected_error_handler,
    validation_error_handler,
)
from app.api.middleware import request_context_middleware
from app.api.router import router
from app.application.document_processing import DocumentProcessingService
from app.application.documents import DocumentService
from app.application.tender_analysis import RelevantChunkSelector, TenderAnalysisService
from app.application.text_chunking import MeaningfulTextChunker
from app.config import LlmProvider, Settings, get_settings
from app.domain.exceptions import ApplicationError
from app.infrastructure.database import Database, DatabaseGateway
from app.infrastructure.database.document_repository import SqlAlchemyDocumentRepository
from app.infrastructure.database.tender_analysis_repository import (
    SqlAlchemyTenderAnalysisRepository,
)
from app.infrastructure.document_storage import LocalDocumentStorage
from app.infrastructure.llm_provider import OpenAICompatibleTenderProvider
from app.infrastructure.pdf_text_extractor import PyMuPdfTextExtractor
from app.logging_config import configure_logging


def create_app(
    settings: Settings | None = None,
    database: DatabaseGateway | None = None,
) -> FastAPI:
    """Создать и настроить экземпляр приложения."""
    resolved_settings = settings or get_settings()
    resolved_database = database or Database(resolved_settings)
    document_service = None
    document_processor = None
    tender_analysis_service = None
    if isinstance(resolved_database, Database):
        document_repository = SqlAlchemyDocumentRepository(resolved_database)
        document_storage = LocalDocumentStorage(resolved_settings.storage_path)
        document_service = DocumentService(
            document_repository,
            document_storage,
            max_size_bytes=resolved_settings.upload_max_size_bytes,
            chunk_size_bytes=resolved_settings.upload_chunk_size_bytes,
        )
        document_processor = DocumentProcessingService(
            document_repository,
            document_storage,
            PyMuPdfTextExtractor(),
            MeaningfulTextChunker(
                max_chars=resolved_settings.text_chunk_size_chars,
                overlap_chars=resolved_settings.text_chunk_overlap_chars,
            ),
        )
        api_key = resolved_settings.llm_api_key.get_secret_value()
        analysis_provider = None
        if resolved_settings.llm_provider == LlmProvider.OLLAMA or api_key:
            analysis_provider = OpenAICompatibleTenderProvider(
                name=resolved_settings.llm_provider.value,
                model=resolved_settings.llm_model,
                base_url=resolved_settings.llm_base_url,
                api_key=api_key or "ollama",
                timeout=resolved_settings.llm_timeout_seconds,
            )
        tender_analysis_service = TenderAnalysisService(
            document_repository,
            SqlAlchemyTenderAnalysisRepository(resolved_database),
            analysis_provider,
            RelevantChunkSelector(
                max_chunks=resolved_settings.analysis_context_max_chunks,
                max_chars=resolved_settings.analysis_context_max_chars,
            ),
        )
    configure_logging(resolved_settings.log_level)
    logger = structlog.get_logger(__name__)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.lifecycle_started = True
        application.state.ready = await resolved_database.connect()
        await logger.ainfo(
            "application_started",
            environment=resolved_settings.environment.value,
            database_ready=application.state.ready,
            version=__version__,
        )
        try:
            yield
        finally:
            application.state.ready = False
            application.state.lifecycle_started = False
            await resolved_database.disconnect()
            await logger.ainfo("application_stopped")

    application = FastAPI(
        title="Tender Intelligence",
        version=__version__,
        debug=resolved_settings.debug,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.database = resolved_database
    application.state.document_service = document_service
    application.state.document_processor = document_processor
    application.state.tender_analysis_service = tender_analysis_service
    application.state.lifecycle_started = False
    application.state.ready = False
    application.middleware("http")(request_context_middleware)
    application.add_exception_handler(ApplicationError, application_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(Exception, unexpected_error_handler)
    application.include_router(router)
    return application


app = create_app()
