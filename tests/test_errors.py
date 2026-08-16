from httpx import ASGITransport, AsyncClient

from app.config import Environment, Settings
from app.domain.exceptions import ApplicationError
from app.main import create_app
from tests.fakes import FakeDatabase


async def test_application_error_has_safe_response() -> None:
    application = create_app(
        Settings(environment=Environment.TEST, log_level="CRITICAL"),
        database=FakeDatabase(),
    )

    @application.get("/expected-error")
    async def expected_error() -> None:
        raise ApplicationError("Документ не найден", code="document_not_found")

    transport = ASGITransport(app=application, raise_app_exceptions=False)
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        response = await client.get("/expected-error", headers={"X-Request-ID": "request-1"})

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Документ не найден",
        "code": "document_not_found",
        "request_id": "request-1",
    }


async def test_unexpected_error_does_not_expose_details() -> None:
    application = create_app(
        Settings(environment=Environment.TEST, log_level="CRITICAL"),
        database=FakeDatabase(),
    )

    @application.get("/unexpected-error")
    async def unexpected_error() -> None:
        raise RuntimeError("Внутренняя техническая информация")

    transport = ASGITransport(app=application, raise_app_exceptions=False)
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        response = await client.get("/unexpected-error", headers={"X-Request-ID": "request-2"})

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Внутренняя ошибка сервера",
        "code": "internal_error",
        "request_id": "request-2",
    }
