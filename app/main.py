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
from app.application.documents import DocumentService
from app.config import Settings, get_settings
from app.domain.exceptions import ApplicationError
from app.infrastructure.database import Database, DatabaseGateway
from app.infrastructure.database.document_repository import SqlAlchemyDocumentRepository
from app.infrastructure.document_storage import LocalDocumentStorage
from app.logging_config import configure_logging


def create_app(
    settings: Settings | None = None,
    database: DatabaseGateway | None = None,
) -> FastAPI:
    """Создать и настроить экземпляр приложения."""
    resolved_settings = settings or get_settings()
    resolved_database = database or Database(resolved_settings)
    document_service = None
    if isinstance(resolved_database, Database):
        document_service = DocumentService(
            SqlAlchemyDocumentRepository(resolved_database),
            LocalDocumentStorage(resolved_settings.storage_path),
            max_size_bytes=resolved_settings.upload_max_size_bytes,
            chunk_size_bytes=resolved_settings.upload_chunk_size_bytes,
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
    application.state.lifecycle_started = False
    application.state.ready = False
    application.middleware("http")(request_context_middleware)
    application.add_exception_handler(ApplicationError, application_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(Exception, unexpected_error_handler)
    application.include_router(router)
    return application


app = create_app()
