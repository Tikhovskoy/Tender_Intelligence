"""Эндпоинты проверки состояния приложения."""

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app import __version__
from app.api.schemas import HealthResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["Состояние сервиса"])


@router.get("/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """Подтвердить, что процесс приложения работает."""
    return HealthResponse(service="tender-intelligence", version=__version__)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
async def readiness(request: Request) -> ReadinessResponse | JSONResponse:
    """Подтвердить готовность приложения обслуживать запросы."""
    if bool(getattr(request.app.state, "ready", False)):
        return ReadinessResponse(status="ready")
    payload = ReadinessResponse(status="not_ready")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )
