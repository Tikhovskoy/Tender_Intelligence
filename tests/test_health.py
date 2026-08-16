from httpx import AsyncClient


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
