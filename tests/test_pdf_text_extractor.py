from pathlib import Path

import pymupdf
import pytest

from app.domain.exceptions import DocumentProcessingError, DocumentTextMissingError
from app.infrastructure.pdf_text_extractor import PyMuPdfTextExtractor


def create_pdf(path: Path, page_texts: list[str]) -> Path:
    with pymupdf.open() as document:  # type: ignore[no-untyped-call]
        for text in page_texts:
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        document.save(path)
    return path


async def test_extractor_preserves_pages_and_text(tmp_path: Path) -> None:
    path = create_pdf(
        tmp_path / "tender.pdf",
        ["Contract amount: 100000 RUB", "Completion period: 30 days"],
    )

    pages = await PyMuPdfTextExtractor().extract(path)

    assert [(page.page_number, page.text) for page in pages] == [
        (1, "Contract amount: 100000 RUB"),
        (2, "Completion period: 30 days"),
    ]


async def test_extractor_rejects_pdf_without_text(tmp_path: Path) -> None:
    path = create_pdf(tmp_path / "scan.pdf", ["", ""])

    with pytest.raises(DocumentTextMissingError, match="OCR") as error:
        await PyMuPdfTextExtractor().extract(path)

    assert error.value.code == "document_text_missing"


async def test_extractor_returns_clear_error_for_corrupted_pdf(tmp_path: Path) -> None:
    path = tmp_path / "corrupted.pdf"
    path.write_bytes(b"%PDF-corrupted")

    with pytest.raises(DocumentProcessingError, match="структуру") as error:
        await PyMuPdfTextExtractor().extract(path)

    assert error.value.code == "pdf_read_failed"
