from fastapi import FastAPI
from httpx import AsyncClient

from app.api.dependencies import get_tender_analysis_service
from app.application.tender_analysis import RelevantChunkSelector, TenderAnalysisService
from tests.fakes import InMemoryDocumentRepository, InMemoryTenderAnalysisRepository
from tests.test_tender_analysis import StubTenderProvider, make_card, prepare_document


async def test_analysis_api_creates_and_returns_card(
    application: FastAPI,
    client: AsyncClient,
) -> None:
    documents = InMemoryDocumentRepository()
    document = await prepare_document(documents)
    service = TenderAnalysisService(
        documents,
        InMemoryTenderAnalysisRepository(),
        StubTenderProvider(make_card()),
        RelevantChunkSelector(max_chunks=5, max_chars=5000),
    )
    application.dependency_overrides[get_tender_analysis_service] = lambda: service

    create_response = await client.post(f"/api/v1/documents/{document.id}/analysis")
    get_response = await client.get(f"/api/v1/documents/{document.id}/analysis")

    assert create_response.status_code == 200
    assert create_response.json()["contract_amount"]["value"] == "100 000"
    assert get_response.status_code == 200
    assert get_response.json() == create_response.json()


async def test_analysis_api_reports_unconfigured_provider(
    application: FastAPI,
    client: AsyncClient,
) -> None:
    documents = InMemoryDocumentRepository()
    document = await prepare_document(documents)
    service = TenderAnalysisService(
        documents,
        InMemoryTenderAnalysisRepository(),
        None,
        RelevantChunkSelector(max_chunks=5, max_chars=5000),
    )
    application.dependency_overrides[get_tender_analysis_service] = lambda: service

    response = await client.post(
        f"/api/v1/documents/{document.id}/analysis",
        headers={"X-Request-ID": "provider-missing"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Провайдер анализа не настроен",
        "code": "analysis_provider_not_configured",
        "request_id": "provider-missing",
    }
