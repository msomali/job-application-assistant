"""Test refresh token endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_refresh_endpoint_exists(client):
    resp = await client.post("/api/auth/refresh")
    # Should return 401 (no cookie), not 404 (missing route)
    assert resp.status_code != 404


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(client):
    resp = await client.post("/api/auth/refresh")
    assert resp.status_code == 401
