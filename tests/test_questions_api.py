from fastapi import FastAPI
from httpx import AsyncClient

from app.api.dependencies import get_rag_service
from app.application.rag import RagService
from app.domain.rag import GroundedAnswerDraft
from tests.fakes import InMemoryDocumentRepository, InMemoryQuestionRepository
from tests.test_rag import StubQuestionProvider, StubVectorSearcher, search_results
from tests.test_tender_analysis import prepare_document


async def test_question_api_creates_answer_and_returns_history(
    application: FastAPI,
    client: AsyncClient,
) -> None:
    documents = InMemoryDocumentRepository()
    document = await prepare_document(documents)
    service = RagService(
        documents,
        StubVectorSearcher(search_results()),
        InMemoryQuestionRepository(),
        StubQuestionProvider(
            GroundedAnswerDraft(
                answer="Исполнитель должен иметь лицензию и подтверждённый опыт.",
                context_sufficient=True,
            )
        ),
        min_relevance=0.2,
    )
    application.dependency_overrides[get_rag_service] = lambda: service

    create_response = await client.post(
        f"/api/v1/documents/{document.id}/questions",
        json={"question": "Какие требования к исполнителю?"},
    )
    history_response = await client.get(f"/api/v1/documents/{document.id}/questions")

    assert create_response.status_code == 201
    assert create_response.json()["context_sufficient"] is True
    assert len(create_response.json()["sources"]) == 2
    assert history_response.status_code == 200
    assert history_response.json()["items"] == [create_response.json()]


async def test_question_api_validates_empty_question(
    application: FastAPI,
    client: AsyncClient,
) -> None:
    documents = InMemoryDocumentRepository()
    document = await prepare_document(documents)
    service = RagService(
        documents,
        StubVectorSearcher([]),
        InMemoryQuestionRepository(),
        None,
        min_relevance=0.2,
    )
    application.dependency_overrides[get_rag_service] = lambda: service

    response = await client.post(
        f"/api/v1/documents/{document.id}/questions",
        json={"question": ""},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "request_validation_error"
