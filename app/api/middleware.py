"""Общие HTTP-middleware приложения."""

from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import Request, Response

logger = structlog.get_logger(__name__)

RequestHandler = Callable[[Request], Awaitable[Response]]


async def request_context_middleware(request: Request, call_next: RequestHandler) -> Response:
    """Добавить request ID и записать результат обработки запроса."""
    incoming_request_id = request.headers.get("X-Request-ID", "").strip()
    request_id = incoming_request_id[:128] if incoming_request_id else str(uuid4())
    request.state.request_id = request_id

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    started_at = perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        await logger.aexception(
            "request_failed",
            method=request.method,
            path=request.url.path,
        )
        raise
    else:
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        await logger.ainfo(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        structlog.contextvars.clear_contextvars()
