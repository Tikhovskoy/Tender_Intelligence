from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Environment, Settings
from app.main import create_app
from tests.fakes import FakeDatabase


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    settings = Settings(environment=Environment.TEST, log_level="CRITICAL")
    application = create_app(settings, database=FakeDatabase())
    transport = ASGITransport(app=application)
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=transport, base_url="http://test") as test_client,
    ):
        yield test_client
