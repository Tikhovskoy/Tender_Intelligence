from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from app.application.vector_search import VectorSearchService
from app.domain.documents import (
    DocumentRecord,
    ExtractedPage,
    StoredDocument,
    TextChunk,
    VectorSearchResult,
)
from app.domain.exceptions import ProviderUnavailableError
from tests.fakes import InMemoryDocumentRepository


class FakeEmbeddingProvider:
    """Детерминированные embeddings без внешнего API."""

    model = "fake-embedding"

    def __init__(self, query_vector: Sequence[float] = (1.0, 0.0)) -> None:
        self.query_vector = query_vector
        self.queries: list[str] = []

    async def embed_documents(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return [[1.0, float(index)] for index, _ in enumerate(texts)]

    async def embed_query(self, text: str) -> Sequence[float]:
        self.queries.append(text)
        return self.query_vector


async def prepare_index(repository: InMemoryDocumentRepository) -> DocumentRecord:
    document = await repository.create(
        StoredDocument(
            original_filename="тендер.pdf",
            stored_filename="тендер.pdf",
            content_type="application/pdf",
            size_bytes=100,
            sha256="b" * 64,
        )
    )
    await repository.mark_processing(document.id)
    await repository.save_content(
        document.id,
        [ExtractedPage(page_number=1, text="Цена и сроки")],
        [
            TextChunk(
                page_number=1,
                chunk_index=0,
                text="Начальная цена контракта",
                char_start=0,
                char_end=25,
                embedding=[1.0, 0.0],
                embedding_model="fake-embedding",
            ),
            TextChunk(
                page_number=1,
                chunk_index=1,
                text="Срок выполнения работ",
                char_start=26,
                char_end=48,
                embedding=[0.0, 1.0],
                embedding_model="fake-embedding",
            ),
        ],
    )
    return document


async def test_search_returns_ranked_chunks_of_selected_document() -> None:
    repository = InMemoryDocumentRepository()
    document = await prepare_index(repository)
    other_document = await prepare_index(repository)
    provider = FakeEmbeddingProvider()
    service = VectorSearchService(repository, provider, top_k=2)

    results = await service.search(document.id, "  Какова цена?  ")

    assert provider.queries == ["Какова цена?"]
    assert [result.chunk_index for result in results] == [0, 1]
    assert results[0].relevance == pytest.approx(1.0)
    assert [result.id for result in results] == [
        uuid5(NAMESPACE_URL, f"{document.id}:0"),
        uuid5(NAMESPACE_URL, f"{document.id}:1"),
    ]
    assert document.id != other_document.id


async def test_search_reports_missing_embedding_provider() -> None:
    repository = InMemoryDocumentRepository()
    document = await prepare_index(repository)
    service = VectorSearchService(repository, None, top_k=5)

    with pytest.raises(ProviderUnavailableError) as error:
        await service.search(document.id, "Какова цена?")

    assert error.value.code == "embedding_provider_not_configured"


def test_reranking_promotes_exact_experience_requirement() -> None:
    candidates = [
        VectorSearchResult(
            id=uuid4(),
            chunk_index=1,
            page_number=7,
            text="Исполнитель обеспечивает техническую поддержку системы.",
            relevance=0.82,
        ),
        VectorSearchResult(
            id=uuid4(),
            chunk_index=2,
            page_number=3,
            text="Опыт работы на рынке не менее 1 года.",
            relevance=0.79,
        ),
    ]

    results = VectorSearchService._rerank(
        "Опыт работы на рынке исполнителя?",
        candidates,
    )

    assert results[0].page_number == 3


def test_reranking_understands_experience_synonym() -> None:
    candidates = [
        VectorSearchResult(
            id=uuid4(),
            chunk_index=1,
            page_number=8,
            text="Подрядчик оказывает техническую поддержку.",
            relevance=0.82,
        ),
        VectorSearchResult(
            id=uuid4(),
            chunk_index=2,
            page_number=3,
            text="Опыт работы на рынке не менее 1 года.",
            relevance=0.76,
        ),
    ]

    results = VectorSearchService._rerank(
        "Какой минимальный стаж требуется от подрядчика?",
        candidates,
    )

    assert results[0].page_number == 3
