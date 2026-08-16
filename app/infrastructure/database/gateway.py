"""Контракт жизненного цикла подключения к базе данных."""

from typing import Protocol


class DatabaseGateway(Protocol):
    """Минимальный интерфейс БД для запуска и healthcheck."""

    async def connect(self) -> bool:
        """Проверить начальное подключение."""
        ...

    async def is_ready(self) -> bool:
        """Проверить доступность БД."""
        ...

    async def disconnect(self) -> None:
        """Освободить ресурсы подключения."""
        ...
