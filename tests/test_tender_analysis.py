from collections.abc import Sequence

import pytest
from pydantic import ValidationError

from app.application.tender_analysis import RelevantChunkSelector, TenderAnalysisService
from app.domain.documents import DocumentRecord, ExtractedPage, StoredDocument, TextChunk
from app.domain.exceptions import InvalidProviderResponseError, ProviderUnavailableError
from app.domain.tender import (
    NOT_FOUND,
    AnalysisChunk,
    SourceCitation,
    SourcedList,
    SourcedText,
    TenderCard,
)
from tests.fakes import InMemoryDocumentRepository, InMemoryTenderAnalysisRepository


def make_card(*, quote: str = "Начальная цена контракта — 100 000 рублей") -> TenderCard:
    source = SourceCitation(page_number=1, quote=quote)
    missing_text = SourcedText(value=NOT_FOUND, sources=[])
    return TenderCard(
        procurement_name=SourcedText(value="Поставка оборудования", sources=[source]),
        customer=missing_text,
        contract_amount=SourcedText(value="100 000", sources=[source]),
        currency=SourcedText(value="рубль", sources=[source]),
        execution_period=missing_text,
        contractor_requirements=SourcedList(items=[NOT_FOUND], sources=[]),
        penalties=SourcedList(items=[NOT_FOUND], sources=[]),
        summary=SourcedText(value="Поставка оборудования на 100 000 рублей", sources=[source]),
    )


class StubTenderProvider:
    """Управляемый провайдер карточки."""

    name = "stub"
    model = "stub-model"

    def __init__(self, card: TenderCard) -> None:
        self.card = card
        self.received_chunks: Sequence[AnalysisChunk] = []

    async def analyze(self, chunks: Sequence[AnalysisChunk]) -> TenderCard:
        self.received_chunks = chunks
        return self.card


async def prepare_document(repository: InMemoryDocumentRepository) -> DocumentRecord:
    document = await repository.create(
        StoredDocument(
            original_filename="тендер.pdf",
            stored_filename="document.pdf",
            content_type="application/pdf",
            size_bytes=100,
            sha256="a" * 64,
        )
    )
    page_text = "Поставка оборудования. Начальная цена контракта — 100 000 рублей."
    await repository.mark_processing(document.id)
    await repository.save_content(
        document.id,
        [ExtractedPage(page_number=1, text=page_text)],
        [
            TextChunk(
                page_number=1,
                chunk_index=0,
                text=page_text,
                char_start=0,
                char_end=len(page_text),
            )
        ],
    )
    ready = await repository.get(document.id)
    assert ready is not None
    return ready


def test_schema_requires_sources_for_found_values() -> None:
    with pytest.raises(ValidationError, match="требуется источник"):
        SourcedText(value="100 000", sources=[])


def test_schema_rejects_sources_for_missing_values() -> None:
    with pytest.raises(ValidationError, match="не допускаются"):
        SourcedList(
            items=[NOT_FOUND],
            sources=[SourceCitation(page_number=1, quote="Нет сведений")],
        )


def test_selector_limits_context_and_covers_keywords() -> None:
    chunks = [
        AnalysisChunk(chunk_index=0, page_number=1, text="Общие сведения о документе"),
        AnalysisChunk(chunk_index=1, page_number=2, text="Начальная цена 500 000 рублей"),
        AnalysisChunk(chunk_index=2, page_number=3, text="Срок выполнения 30 дней"),
        AnalysisChunk(chunk_index=3, page_number=4, text="Штраф за просрочку работ"),
    ]

    selected = RelevantChunkSelector(max_chunks=3, max_chars=1000).select(chunks)

    assert len(selected) == 3
    assert selected[0].chunk_index == 0
    assert any("цена" in chunk.text for chunk in selected)
    assert any("штраф" in chunk.text or "Срок" in chunk.text for chunk in selected)


async def test_service_saves_validated_card() -> None:
    documents = InMemoryDocumentRepository()
    document = await prepare_document(documents)
    analyses = InMemoryTenderAnalysisRepository()
    provider = StubTenderProvider(make_card())
    service = TenderAnalysisService(
        documents,
        analyses,
        provider,
        RelevantChunkSelector(max_chunks=5, max_chars=5000),
    )

    result = await service.analyze(document.id)

    assert result.contract_amount.value == "100 000"
    assert provider.received_chunks[0].page_number == 1
    assert analyses.saved_metadata == ("stub", "stub-model", "2")
    assert await service.get(document.id) == result


async def test_service_rejects_invented_source() -> None:
    documents = InMemoryDocumentRepository()
    document = await prepare_document(documents)
    analyses = InMemoryTenderAnalysisRepository()
    service = TenderAnalysisService(
        documents,
        analyses,
        StubTenderProvider(make_card(quote="Такой цитаты в документе нет")),
        RelevantChunkSelector(max_chunks=5, max_chars=5000),
    )

    with pytest.raises(InvalidProviderResponseError) as error:
        await service.analyze(document.id)

    assert error.value.code == "invalid_analysis_source"
    assert document.id not in analyses.cards


async def test_service_reports_missing_provider() -> None:
    documents = InMemoryDocumentRepository()
    document = await prepare_document(documents)
    service = TenderAnalysisService(
        documents,
        InMemoryTenderAnalysisRepository(),
        None,
        RelevantChunkSelector(max_chunks=5, max_chars=5000),
    )

    with pytest.raises(ProviderUnavailableError) as error:
        await service.analyze(document.id)

    assert error.value.code == "analysis_provider_not_configured"
