"""Хранение вопросов, ответов и источников."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domain.rag import (
    GroundedAnswerDraft,
    QuestionRepository,
    RagAnswer,
    RagSource,
)
from app.infrastructure.database.connection import Database
from app.infrastructure.database.models import AnswerSource, Question


class SqlAlchemyQuestionRepository(QuestionRepository):
    """Транзакционное сохранение истории RAG-вопросов."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def save(
        self,
        document_id: UUID,
        question: str,
        draft: GroundedAnswerDraft,
        sources: Sequence[RagSource],
        *,
        provider: str,
        model: str,
    ) -> RagAnswer:
        async with self.database.session() as session:
            record = Question(
                document_id=document_id,
                question=question,
                answer=draft.answer,
                context_sufficient=draft.context_sufficient,
                provider=provider,
                model=model,
            )
            session.add(record)
            await session.flush()
            session.add_all(
                AnswerSource(
                    question_id=record.id,
                    chunk_id=source.chunk_id,
                    page_number=source.page_number,
                    quote=source.quote,
                    relevance=source.relevance,
                    position=source.position,
                )
                for source in sources
            )
            await session.commit()
        return RagAnswer(
            id=record.id,
            document_id=record.document_id,
            question=record.question,
            answer=record.answer,
            context_sufficient=record.context_sufficient,
            sources=list(sources),
            created_at=record.created_at,
        )

    async def list(self, document_id: UUID, *, limit: int) -> Sequence[RagAnswer]:
        statement = (
            select(Question)
            .options(selectinload(Question.sources))
            .where(Question.document_id == document_id)
            .order_by(Question.created_at.desc(), Question.id.desc())
            .limit(limit)
        )
        async with self.database.session() as session:
            records = (await session.scalars(statement)).all()
        return [self._to_domain(record) for record in records]

    @staticmethod
    def _to_domain(record: Question) -> RagAnswer:
        return RagAnswer(
            id=record.id,
            document_id=record.document_id,
            question=record.question,
            answer=record.answer,
            context_sufficient=record.context_sufficient,
            sources=[
                RagSource(
                    chunk_id=source.chunk_id,
                    page_number=source.page_number,
                    quote=source.quote,
                    relevance=source.relevance,
                    position=source.position,
                )
                for source in sorted(record.sources, key=lambda item: item.position)
            ],
            created_at=record.created_at,
        )
