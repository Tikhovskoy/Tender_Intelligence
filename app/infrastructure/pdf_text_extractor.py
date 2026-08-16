"""Извлечение текстового слоя из PDF."""

from collections.abc import Sequence
from functools import partial
from pathlib import Path

import anyio
import pymupdf

from app.domain.documents import ExtractedPage
from app.domain.exceptions import DocumentProcessingError, DocumentTextMissingError


class PyMuPdfTextExtractor:
    """Постраничное извлечение текста без OCR."""

    async def extract(self, path: Path) -> Sequence[ExtractedPage]:
        """Выполнить блокирующую работу с PDF в отдельном потоке."""
        return await anyio.to_thread.run_sync(partial(self._extract_sync, path))

    @staticmethod
    def _extract_sync(path: Path) -> list[ExtractedPage]:
        if not path.is_file():
            raise DocumentProcessingError(
                "Исходный PDF не найден в хранилище",
                code="source_file_missing",
            )

        try:
            with pymupdf.open(path) as document:  # type: ignore[no-untyped-call]
                if document.needs_pass:
                    raise DocumentProcessingError(
                        "PDF защищён паролем и не может быть обработан",
                        code="pdf_password_required",
                    )
                pages = [
                    ExtractedPage(
                        page_number=index + 1,
                        text=page.get_text("text", sort=True).strip(),
                    )
                    for index, page in enumerate(document)
                ]
        except DocumentProcessingError:
            raise
        except (pymupdf.FileDataError, RuntimeError, ValueError) as error:
            raise DocumentProcessingError(
                "Не удалось прочитать структуру PDF",
                code="pdf_read_failed",
            ) from error

        if not any(page.text for page in pages):
            raise DocumentTextMissingError(
                "PDF не содержит извлекаемого текста. OCR сканов не поддерживается",
                code="document_text_missing",
            )
        return pages
