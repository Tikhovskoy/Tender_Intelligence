from hashlib import sha256
from pathlib import Path

import pytest

from app.domain.exceptions import FileTooLargeError, InvalidDocumentError
from app.infrastructure.document_storage import LocalDocumentStorage

PDF_CONTENT = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF"


class MemoryReader:
    """Асинхронное чтение байтов из памяти."""

    def __init__(self, content: bytes) -> None:
        self.content = content
        self.position = 0

    async def read(self, size: int = -1) -> bytes:
        if self.position >= len(self.content):
            return b""
        end = len(self.content) if size < 0 else self.position + size
        chunk = self.content[self.position : end]
        self.position += len(chunk)
        return chunk


async def test_pdf_is_saved_atomically(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(tmp_path)

    stored = await storage.save_pdf(
        MemoryReader(PDF_CONTENT),
        original_filename="тендер.pdf",
        content_type="application/pdf",
        max_size_bytes=1024,
        chunk_size_bytes=8,
    )

    saved_path = tmp_path / stored.stored_filename
    assert saved_path.read_bytes() == PDF_CONTENT
    assert stored.size_bytes == len(PDF_CONTENT)
    assert stored.sha256 == sha256(PDF_CONTENT).hexdigest()
    assert not list(tmp_path.glob("*.part"))


async def test_invalid_signature_is_rejected_and_cleaned(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(tmp_path)

    with pytest.raises(InvalidDocumentError, match="PDF-сигнатуру"):
        await storage.save_pdf(
            MemoryReader(b"not-a-pdf"),
            original_filename="подмена.pdf",
            content_type="application/pdf",
            max_size_bytes=1024,
            chunk_size_bytes=8,
        )

    assert not list(tmp_path.iterdir())


async def test_oversized_file_is_rejected_and_cleaned(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(tmp_path)

    with pytest.raises(FileTooLargeError, match="превышает"):
        await storage.save_pdf(
            MemoryReader(PDF_CONTENT),
            original_filename="большой.pdf",
            content_type="application/pdf",
            max_size_bytes=10,
            chunk_size_bytes=8,
        )

    assert not list(tmp_path.iterdir())


async def test_storage_rejects_unsafe_internal_name(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(tmp_path)

    with pytest.raises(ValueError, match="внутреннее имя"):
        await storage.delete("../document.pdf")
