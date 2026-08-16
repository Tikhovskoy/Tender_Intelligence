"""ORM-модели документов, анализа и вопросов."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.documents import DocumentStatus
from app.infrastructure.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Загруженный исходный документ."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="size_bytes_non_negative"),
        CheckConstraint("page_count IS NULL OR page_count >= 0", name="page_count_non_negative"),
        Index("ix_documents_status_created_at", "status", "created_at"),
    )

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus,
            name="document_status",
            values_callable=lambda enum_type: [item.value for item in enum_type],
        ),
        nullable=False,
        default=DocumentStatus.UPLOADED,
        server_default=DocumentStatus.UPLOADED.value,
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)

    pages: Mapped[list[DocumentPage]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    analysis: Mapped[TenderAnalysis | None] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    questions: Mapped[list[Question]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DocumentPage(UUIDPrimaryKeyMixin, Base):
    """Текст одной страницы PDF."""

    __tablename__ = "document_pages"
    __table_args__ = (
        CheckConstraint("page_number > 0", name="page_number_positive"),
        UniqueConstraint("document_id", "page_number"),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    document: Mapped[Document] = relationship(back_populates="pages")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="page",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DocumentChunk(UUIDPrimaryKeyMixin, Base):
    """Фрагмент страницы с векторным представлением."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="chunk_index_non_negative"),
        CheckConstraint("char_start >= 0", name="char_start_non_negative"),
        CheckConstraint("char_end > char_start", name="char_range_valid"),
        UniqueConstraint("document_id", "chunk_index"),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector())
    embedding_model: Mapped[str | None] = mapped_column(String(255))
    attributes: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    document: Mapped[Document] = relationship(back_populates="chunks")
    page: Mapped[DocumentPage] = relationship(back_populates="chunks")
    answer_sources: Mapped[list[AnswerSource]] = relationship(
        back_populates="chunk",
        passive_deletes=True,
    )


class TenderAnalysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Структурированная карточка тендера."""

    __tablename__ = "tender_analyses"

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)

    document: Mapped[Document] = relationship(back_populates="analysis")


class Question(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Вопрос пользователя и сформированный ответ."""

    __tablename__ = "questions"

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    context_sufficient: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)

    document: Mapped[Document] = relationship(back_populates="questions")
    sources: Mapped[list[AnswerSource]] = relationship(
        back_populates="question_record",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AnswerSource.position",
    )


class AnswerSource(UUIDPrimaryKeyMixin, Base):
    """Подтверждающий источник ответа."""

    __tablename__ = "answer_sources"
    __table_args__ = (
        CheckConstraint("page_number > 0", name="page_number_positive"),
        CheckConstraint("position > 0", name="position_positive"),
        CheckConstraint(
            "relevance >= -1 AND relevance <= 1",
            name="relevance_range",
        ),
        UniqueConstraint("question_id", "position"),
    )

    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    relevance: Mapped[float] = mapped_column(Float, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    question_record: Mapped[Question] = relationship(back_populates="sources")
    chunk: Mapped[DocumentChunk] = relationship(back_populates="answer_sources")
