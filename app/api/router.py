"""Корневой маршрутизатор приложения."""

from fastapi import APIRouter

from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.tender_analysis import router as tender_analysis_router

router = APIRouter()
router.include_router(health_router)
router.include_router(documents_router)
router.include_router(tender_analysis_router)
