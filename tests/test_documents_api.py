from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from httpx import AsyncClient

from app.api.dependencies import get_document_processor, get_document_service
from app.application.document_processing import DocumentProcessingService
from app.application.documents import DocumentService
from app.domain.documents import ExtractedPage
from app.infrastructure.document_storage import LocalDocumentStorage
from tests.fakes import InMemoryDocumentRepository
from tests.test_document_processing import StaticExtractor
from tests.test_document_storage import PDF_CONTENT


def configure_service(application: FastAPI, tmp_path: Path, *, max_size: int = 1024) -> None:
    service = DocumentService(
        InMemoryDocumentRepository(),
        LocalDocumentStorage(tmp_path),
        max_size_bytes=max_size,
        chunk_size_bytes=8,
    )
    application.dependency_overrides[get_document_service] = lambda: service


async def test_document_api_flow(
    application: FastAPI,
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    configure_service(application, tmp_path)

    upload_response = await client.post(
        "/api/v1/documents",
        files={"file": ("тендер.pdf", PDF_CONTENT, "application/pdf")},
    )

    assert upload_response.status_code == 201
    uploaded = upload_response.json()
    assert uploaded["original_filename"] == "тендер.pdf"
    assert uploaded["status"] == "uploaded"

    get_response = await client.get(f"/api/v1/documents/{uploaded['id']}")
    list_response = await client.get("/api/v1/documents")

    assert get_response.status_code == 200
    assert get_response.json()["id"] == uploaded["id"]
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()["items"]] == [uploaded["id"]]


async def test_api_rejects_invalid_file_type(
    application: FastAPI,
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    configure_service(application, tmp_path)

    response = await client.post(
        "/api/v1/documents",
        files={"file": ("тендер.txt", b"text", "text/plain")},
        headers={"X-Request-ID": "invalid-file"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Допускаются только файлы PDF",
        "code": "file_extension_invalid",
        "request_id": "invalid-file",
    }


async def test_api_rejects_oversized_file(
    application: FastAPI,
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    configure_service(application, tmp_path, max_size=10)

    response = await client.post(
        "/api/v1/documents",
        files={"file": ("тендер.pdf", PDF_CONTENT, "application/pdf")},
    )

    assert response.status_code == 413
    assert response.json()["code"] == "file_too_large"


async def test_api_returns_not_found(
    application: FastAPI,
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    configure_service(application, tmp_path)

    response = await client.get(f"/api/v1/documents/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["code"] == "document_not_found"


async def test_upload_starts_background_processing(
    application: FastAPI,
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    repository = InMemoryDocumentRepository()
    storage = LocalDocumentStorage(tmp_path)
    service = DocumentService(
        repository,
        storage,
        max_size_bytes=1024,
        chunk_size_bytes=8,
    )
    processor = DocumentProcessingService(
        repository,
        storage,
        StaticExtractor([ExtractedPage(page_number=1, text="Условия контракта")]),
    )
    application.dependency_overrides[get_document_service] = lambda: service
    application.dependency_overrides[get_document_processor] = lambda: processor

    upload_response = await client.post(
        "/api/v1/documents",
        files={"file": ("тендер.pdf", PDF_CONTENT, "application/pdf")},
    )
    document_id = upload_response.json()["id"]
    get_response = await client.get(f"/api/v1/documents/{document_id}")

    assert upload_response.status_code == 201
    assert upload_response.json()["status"] == "uploaded"
    assert get_response.json()["status"] == "ready"
    assert get_response.json()["page_count"] == 1
