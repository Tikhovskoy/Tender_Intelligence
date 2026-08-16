"""Хранение структурированных карточек тендеров."""

from uuid import UUID

from sqlalchemy import select

from app.domain.tender import TenderAnalysisRepository, TenderCard
from app.infrastructure.database.connection import Database
from app.infrastructure.database.models import TenderAnalysis


class SqlAlchemyTenderAnalysisRepository(TenderAnalysisRepository):
    """Сохранение карточек в PostgreSQL JSONB."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def get(self, document_id: UUID) -> TenderCard | None:
        statement = select(TenderAnalysis).where(TenderAnalysis.document_id == document_id)
        async with self.database.session() as session:
            model = await session.scalar(statement)
        return TenderCard.model_validate(model.data) if model is not None else None

    async def save(
        self,
        document_id: UUID,
        card: TenderCard,
        *,
        provider: str,
        model: str,
        prompt_version: str,
    ) -> TenderCard:
        statement = select(TenderAnalysis).where(TenderAnalysis.document_id == document_id)
        async with self.database.session() as session:
            record = await session.scalar(statement)
            if record is None:
                record = TenderAnalysis(document_id=document_id)
                session.add(record)
            record.data = card.model_dump(mode="json")
            record.provider = provider
            record.model = model
            record.prompt_version = prompt_version
            await session.commit()
        return card
