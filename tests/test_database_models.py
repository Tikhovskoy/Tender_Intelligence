from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum

from app.infrastructure.database.base import Base
from app.infrastructure.database.models import Document, DocumentChunk


def test_metadata_contains_all_initial_tables() -> None:
    assert set(Base.metadata.tables) == {
        "answer_sources",
        "document_chunks",
        "document_pages",
        "documents",
        "questions",
        "tender_analyses",
    }


def test_document_status_uses_expected_values() -> None:
    status_type = Document.__table__.c.status.type

    assert isinstance(status_type, Enum)
    assert status_type.enums == ["uploaded", "processing", "ready", "failed"]


def test_chunk_embedding_uses_pgvector() -> None:
    embedding_type = DocumentChunk.__table__.c.embedding.type

    assert isinstance(embedding_type, Vector)


def test_sources_are_deleted_with_chunks() -> None:
    sources_table = Base.metadata.tables["answer_sources"]
    chunk_foreign_key = next(
        foreign_key
        for foreign_key in sources_table.foreign_keys
        if foreign_key.column.table.name == "document_chunks"
    )

    assert chunk_foreign_key.ondelete == "CASCADE"
