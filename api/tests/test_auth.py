"""Test auth endpoints exist and return expected status codes."""

import pytest


@pytest.mark.asyncio
async def test_login_endpoint_exists(client):
    """Auth login route should exist (not 404/405 on the path)."""
    resp = await client.post("/api/auth/login", data={"username": "x", "password": "x"})
    # fastapi-users returns 400 for bad credentials, not 404/405
    assert resp.status_code not in (404, 405)


@pytest.mark.asyncio
async def test_register_endpoint_exists(client):
    """Auth register route should exist — verify via invalid payload (422)."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": "not-an-email"},  # Missing password triggers 422
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_verify_endpoint_exists(client):
    """Auth verify route should exist."""
    resp = await client.post("/api/auth/verify", json={"token": "fake"})
    assert resp.status_code not in (404, 405)


@pytest.mark.asyncio
async def test_forgot_password_endpoint_exists(client):
    """Auth forgot-password route should exist."""
    resp = await client.post(
        "/api/auth/forgot-password", json={"email": "test@example.com"}
    )
    assert resp.status_code not in (404, 405)
