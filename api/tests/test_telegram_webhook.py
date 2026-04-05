"""Test Telegram webhook endpoints."""

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
async def test_webhook_endpoint_exists(client):
    resp = await client.post("/api/telegram/webhook/fake-token", json={})
    # Should not be 404
    assert resp.status_code != 404


@pytest.mark.asyncio
async def test_link_code_requires_auth(client):
    resp = await client.post("/api/telegram/link-code")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_status_requires_auth(client):
    resp = await client.get("/api/telegram/status")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unlink_requires_auth(client):
    resp = await client.delete("/api/telegram/unlink")
    assert resp.status_code == 401
