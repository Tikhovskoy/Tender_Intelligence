from pathlib import Path
from uuid import uuid4

import pytest

from app.application.documents import DocumentService
from app.domain.documents import DocumentRecord, StoredDocument
from app.domain.exceptions import DocumentNotFoundError, InvalidDocumentError
from app.infrastructure.document_storage import LocalDocumentStorage
from tests.fakes import InMemoryDocumentRepository
from tests.test_document_storage import PDF_CONTENT, MemoryReader


def build_service(tmp_path: Path) -> DocumentService:
    return DocumentService(
        InMemoryDocumentRepository(),
        LocalDocumentStorage(tmp_path),
        max_size_bytes=1024,
        chunk_size_bytes=8,
    )


async def test_upload_normalizes_browser_path(tmp_path: Path) -> None:
    service = build_service(tmp_path)

    record = await service.upload(
        MemoryReader(PDF_CONTENT),
        filename=r"C:\fakepath\тендер.PDF",
        content_type="application/pdf",
    )

    assert record.original_filename == "тендер.PDF"
    assert record.status == "uploaded"


@pytest.mark.parametrize(
    ("filename", "content_type", "error_code"),
    [
        ("тендер.txt", "application/pdf", "file_extension_invalid"),
        ("тендер.pdf", "text/plain", "content_type_invalid"),
        (None, "application/pdf", "filename_missing"),
    ],
)
async def test_upload_rejects_invalid_metadata(
    tmp_path: Path,
    filename: str | None,
    content_type: str,
    error_code: str,
) -> None:
    service = build_service(tmp_path)

    with pytest.raises(InvalidDocumentError) as error:
        await service.upload(
            MemoryReader(PDF_CONTENT),
            filename=filename,
            content_type=content_type,
        )

    assert error.value.code == error_code
    assert not any(tmp_path.iterdir())


async def test_get_missing_document_returns_domain_error(tmp_path: Path) -> None:
    service = build_service(tmp_path)

    with pytest.raises(DocumentNotFoundError, match="не найден"):
        await service.get(uuid4())


async def test_upload_removes_file_when_repository_fails(tmp_path: Path) -> None:
    class FailingRepository(InMemoryDocumentRepository):
        async def create(self, document: StoredDocument) -> DocumentRecord:
            raise RuntimeError("database unavailable")

    service = DocumentService(
        FailingRepository(),
        LocalDocumentStorage(tmp_path),
        max_size_bytes=1024,
        chunk_size_bytes=8,
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        await service.upload(
            MemoryReader(PDF_CONTENT),
            filename="тендер.pdf",
            content_type="application/pdf",
        )

    assert not any(tmp_path.iterdir())
