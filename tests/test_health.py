from httpx import ASGITransport, AsyncClient

from app.config import Environment, Settings
from app.main import create_app
from tests.fakes import FakeDatabase


async def test_liveness(client: AsyncClient) -> None:
    response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "tender-intelligence",
        "version": "0.1.0",
    }


async def test_readiness(client: AsyncClient) -> None:
    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_request_id_is_returned(client: AsyncClient) -> None:
    response = await client.get("/health/live", headers={"X-Request-ID": "demo-request"})

    assert response.headers["X-Request-ID"] == "demo-request"


async def test_readiness_reports_unavailable_database() -> None:
    database = FakeDatabase(ready=False)
    application = create_app(
        Settings(environment=Environment.TEST, log_level="CRITICAL"),
        database=database,
    )
    transport = ASGITransport(app=application)
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=transport, base_url="http://test") as test_client,
    ):
        response = await test_client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
