"""Преобразование исключений в безопасные HTTP-ответы."""

from typing import Any, cast

import structlog
from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.exceptions import ApplicationError

logger = structlog.get_logger(__name__)


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))


async def application_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Вернуть ожидаемую прикладную ошибку без трассировки."""
    application_error = cast(ApplicationError, exc)
    await logger.awarning("application_error", error_code=application_error.code)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": application_error.message,
            "code": application_error.code,
            "request_id": _request_id(request),
        },
    )


async def validation_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Вернуть понятную ошибку валидации запроса."""
    validation_error = cast(RequestValidationError, exc)
    errors: list[dict[str, Any]] = jsonable_encoder(validation_error.errors())
    await logger.awarning("request_validation_error", errors=errors)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Некорректные данные запроса",
            "code": "request_validation_error",
            "request_id": _request_id(request),
            "errors": errors,
        },
    )


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Скрыть внутренние детали неожиданной ошибки."""
    await logger.aexception("unexpected_error", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Внутренняя ошибка сервера",
            "code": "internal_error",
            "request_id": _request_id(request),
        },
    )
