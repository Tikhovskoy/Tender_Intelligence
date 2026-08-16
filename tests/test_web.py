from pathlib import Path

from fastapi import FastAPI
from httpx import AsyncClient

from app.api.dependencies import (
    get_document_service,
    get_rag_service,
    get_tender_analysis_service,
)
from app.application.documents import DocumentService
from app.application.rag import RagService
from app.application.tender_analysis import RelevantChunkSelector, TenderAnalysisService
from app.domain.rag import GroundedAnswerDraft
from app.infrastructure.document_storage import LocalDocumentStorage
from tests.fakes import (
    InMemoryDocumentRepository,
    InMemoryQuestionRepository,
    InMemoryTenderAnalysisRepository,
)
from tests.test_document_storage import PDF_CONTENT
from tests.test_rag import StubQuestionProvider, StubVectorSearcher, search_results
from tests.test_tender_analysis import StubTenderProvider, make_card, prepare_document


def configure_web_services(
    application: FastAPI,
    tmp_path: Path,
) -> tuple[
    InMemoryDocumentRepository,
    TenderAnalysisService,
    RagService,
]:
    documents = InMemoryDocumentRepository()
    document_service = DocumentService(
        documents,
        LocalDocumentStorage(tmp_path),
        max_size_bytes=1024,
        chunk_size_bytes=8,
    )
    analysis_service = TenderAnalysisService(
        documents,
        InMemoryTenderAnalysisRepository(),
        StubTenderProvider(make_card()),
        RelevantChunkSelector(max_chunks=5, max_chars=5000),
    )
    rag_service = RagService(
        documents,
        StubVectorSearcher(search_results()),
        InMemoryQuestionRepository(),
        StubQuestionProvider(
            GroundedAnswerDraft(
                answer="Нужны лицензия и опыт работы не менее трёх лет.",
                context_sufficient=True,
            )
        ),
        min_relevance=0.2,
    )
    application.dependency_overrides[get_document_service] = lambda: document_service
    application.dependency_overrides[get_tender_analysis_service] = lambda: analysis_service
    application.dependency_overrides[get_rag_service] = lambda: rag_service
    return documents, analysis_service, rag_service


async def test_home_page_contains_upload_form(
    application: FastAPI,
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    configure_web_services(application, tmp_path)

    response = await client.get("/")

    assert response.status_code == 200
    assert "Разберите объёмный PDF" in response.text
    assert 'hx-post="/documents"' in response.text
    assert "/static/vendor/htmx-2.0.10.min.js" in response.text


async def test_htmx_upload_redirects_to_document(
    application: FastAPI,
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    configure_web_services(application, tmp_path)

    response = await client.post(
        "/documents",
        files={"file": ("условия.pdf", PDF_CONTENT, "application/pdf")},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert response.headers["HX-Redirect"].startswith("/documents/")


async def test_document_page_renders_analysis_and_answer(
    application: FastAPI,
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    documents, analyses, rag = configure_web_services(application, tmp_path)
    document = await prepare_document(documents)
    await analyses.analyze(document.id)
    await rag.ask(document.id, "Какие требования предъявляются к исполнителю?")

    response = await client.get(f"/documents/{document.id}")

    assert response.status_code == 200
    assert "Документ готов к работе" in response.text
    assert "1 страница" in response.text
    assert "Поставка оборудования" in response.text
    assert "Нужны лицензия и опыт работы" in response.text
    assert "Страница 2" in response.text


async def test_question_form_returns_answer_fragment(
    application: FastAPI,
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    documents, _, _ = configure_web_services(application, tmp_path)
    document = await prepare_document(documents)

    response = await client.post(
        f"/documents/{document.id}/questions",
        data={"question": "Какие требования предъявляются к исполнителю?"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "Подтверждено источниками" in response.text
    assert "93% релевантности" in response.text


async def test_htmx_provider_error_is_visible(
    application: FastAPI,
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    documents, _, rag = configure_web_services(application, tmp_path)
    document = await prepare_document(documents)
    rag.provider = None

    response = await client.post(
        f"/documents/{document.id}/questions",
        data={"question": "Какова цена контракта?"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "Провайдер ответов не настроен" in response.text
