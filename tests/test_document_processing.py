from collections.abc import Sequence
from pathlib import Path

from app.application.document_processing import DocumentProcessingService
from app.application.documents import DocumentService
from app.application.text_chunking import MeaningfulTextChunker
from app.domain.documents import DocumentRecord, ExtractedPage
from app.domain.exceptions import DocumentTextMissingError
from app.infrastructure.document_storage import LocalDocumentStorage
from tests.fakes import InMemoryDocumentRepository
from tests.test_document_storage import PDF_CONTENT, MemoryReader


class StaticExtractor:
    """Управляемое извлечение страниц без чтения PDF."""

    def __init__(self, pages: Sequence[ExtractedPage]) -> None:
        self.pages = pages

    async def extract(self, path: Path) -> Sequence[ExtractedPage]:
        return self.pages


class MissingTextExtractor:
    """Имитация документа без текстового слоя."""

    async def extract(self, path: Path) -> Sequence[ExtractedPage]:
        raise DocumentTextMissingError(
            "PDF не содержит извлекаемого текста. OCR сканов не поддерживается",
            code="document_text_missing",
        )


async def upload_document(
    repository: InMemoryDocumentRepository,
    storage: LocalDocumentStorage,
) -> DocumentRecord:
    service = DocumentService(
        repository,
        storage,
        max_size_bytes=1024,
        chunk_size_bytes=8,
    )
    return await service.upload(
        MemoryReader(PDF_CONTENT),
        filename="тендер.pdf",
        content_type="application/pdf",
    )


async def test_processing_saves_pages_and_sets_ready(tmp_path: Path) -> None:
    repository = InMemoryDocumentRepository()
    storage = LocalDocumentStorage(tmp_path)
    document = await upload_document(repository, storage)
    pages = [
        ExtractedPage(page_number=1, text="Цена контракта"),
        ExtractedPage(page_number=2, text="Срок выполнения"),
    ]
    processor = DocumentProcessingService(
        repository,
        storage,
        StaticExtractor(pages),
        MeaningfulTextChunker(max_chars=100, overlap_chars=10),
    )

    await processor.process(document.id)

    updated = await repository.get(document.id)
    assert updated is not None
    assert updated.status == "ready"
    assert updated.page_count == 2
    assert repository.pages[document.id] == pages
    assert [chunk.page_number for chunk in repository.chunks[document.id]] == [1, 2]


async def test_processing_stores_clear_failure(tmp_path: Path) -> None:
    repository = InMemoryDocumentRepository()
    storage = LocalDocumentStorage(tmp_path)
    document = await upload_document(repository, storage)
    processor = DocumentProcessingService(
        repository,
        storage,
        MissingTextExtractor(),
        MeaningfulTextChunker(max_chars=100, overlap_chars=10),
    )

    await processor.process(document.id)

    updated = await repository.get(document.id)
    assert updated is not None
    assert updated.status == "failed"
    assert updated.page_count is None
    assert updated.error_message == (
        "PDF не содержит извлекаемого текста. OCR сканов не поддерживается"
    )
