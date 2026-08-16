from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.application.rag import RagService
from app.domain.documents import VectorSearchResult
from app.domain.rag import ANSWER_NOT_FOUND, GroundedAnswerDraft
from tests.fakes import InMemoryDocumentRepository, InMemoryQuestionRepository
from tests.test_tender_analysis import prepare_document


class StubVectorSearcher:
    """Управляемая выдача семантического поиска."""

    def __init__(self, results: Sequence[VectorSearchResult]) -> None:
        self.results = results
        self.questions: list[str] = []

    async def search(
        self,
        document_id: UUID,
        question: str,
    ) -> Sequence[VectorSearchResult]:
        self.questions.append(question)
        return self.results


class StubQuestionProvider:
    """Управляемый ответ без внешнего API."""

    name = "stub"
    model = "stub-answer-model"

    def __init__(self, draft: GroundedAnswerDraft) -> None:
        self.draft = draft
        self.calls = 0

    async def answer_question(
        self,
        question: str,
        chunks: Sequence[VectorSearchResult],
    ) -> GroundedAnswerDraft:
        self.calls += 1
        return self.draft


def search_results() -> list[VectorSearchResult]:
    return [
        VectorSearchResult(
            id=uuid4(),
            chunk_index=0,
            page_number=2,
            text="Исполнитель должен иметь лицензию и опыт не менее трёх лет.",
            relevance=0.93,
        ),
        VectorSearchResult(
            id=uuid4(),
            chunk_index=1,
            page_number=4,
            text="Требуется предоставить копии лицензий в составе заявки.",
            relevance=0.81,
        ),
        VectorSearchResult(
            id=uuid4(),
            chunk_index=2,
            page_number=7,
            text="Общие положения контракта.",
            relevance=0.05,
        ),
    ]


def test_insufficient_draft_requires_standard_answer() -> None:
    with pytest.raises(ValidationError, match="стандартный ответ"):
        GroundedAnswerDraft(answer="Не знаю", context_sufficient=False)


async def test_rag_answer_contains_ranked_sources() -> None:
    documents = InMemoryDocumentRepository()
    document = await prepare_document(documents)
    questions = InMemoryQuestionRepository()
    provider = StubQuestionProvider(
        GroundedAnswerDraft(
            answer="Нужны лицензия и опыт работы не менее трёх лет.",
            context_sufficient=True,
        )
    )
    searcher = StubVectorSearcher(search_results())
    service = RagService(
        documents,
        searcher,
        questions,
        provider,
        min_relevance=0.2,
    )

    answer = await service.ask(document.id, "  Какие требования к исполнителю?  ")

    assert answer.context_sufficient is True
    assert [source.page_number for source in answer.sources] == [2, 4]
    assert [source.position for source in answer.sources] == [1, 2]
    assert searcher.questions == ["Какие требования к исполнителю?"]
    assert questions.saved_metadata == ("stub", "stub-answer-model")
    assert await service.list_answers(document.id, limit=20) == [answer]


async def test_rag_does_not_call_provider_when_context_is_insufficient() -> None:
    documents = InMemoryDocumentRepository()
    document = await prepare_document(documents)
    questions = InMemoryQuestionRepository()
    provider = StubQuestionProvider(GroundedAnswerDraft(answer="unused", context_sufficient=True))
    service = RagService(
        documents,
        StubVectorSearcher(search_results()[:1]),
        questions,
        provider,
        min_relevance=0.2,
    )

    answer = await service.ask(document.id, "Предусмотрены ли штрафы?")

    assert answer.answer == ANSWER_NOT_FOUND
    assert answer.context_sufficient is False
    assert len(answer.sources) == 1
    assert provider.calls == 0
