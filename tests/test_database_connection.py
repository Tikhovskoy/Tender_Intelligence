from pydantic import SecretStr

from app.config import Environment, Settings
from app.infrastructure.database import Database


async def test_unavailable_database_returns_not_ready() -> None:
    settings = Settings(
        environment=Environment.TEST,
        database_url=SecretStr(
            "postgresql+asyncpg://tender:tender@127.0.0.1:1/tender_intelligence"
        ),
        database_connect_timeout=0.1,
    )
    database = Database(settings)

    try:
        assert await database.connect() is False
        assert await database.is_ready() is False
    finally:
        await database.disconnect()
