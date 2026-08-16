from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.config import Environment, Settings
from app.main import create_app
from tests.fakes import FakeDatabase


@pytest.fixture
def application() -> FastAPI:
    settings = Settings(environment=Environment.TEST, log_level="CRITICAL")
    return create_app(settings, database=FakeDatabase())


@pytest.fixture
async def client(application: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=application)
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=transport, base_url="http://test") as test_client,
    ):
        yield test_client
