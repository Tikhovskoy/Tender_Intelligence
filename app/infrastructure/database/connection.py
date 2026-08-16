"""Управление асинхронным подключением SQLAlchemy."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings


class Database:
    """Подключение к PostgreSQL и фабрика транзакционных сессий."""

    def __init__(self, settings: Settings) -> None:
        self.engine: AsyncEngine = create_async_engine(
            settings.database_url.get_secret_value(),
            echo=settings.database_echo,
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            pool_timeout=settings.database_pool_timeout,
            connect_args={"timeout": settings.database_connect_timeout},
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def connect(self) -> bool:
        """Проверить подключение при запуске приложения."""
        return await self.is_ready()

    async def is_ready(self) -> bool:
        """Выполнить безопасную проверку соединения."""
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except (OSError, SQLAlchemyError):
            return False
        return True

    async def disconnect(self) -> None:
        """Закрыть пул соединений."""
        await self.engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Открыть сессию с автоматическим откатом при ошибке."""
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
