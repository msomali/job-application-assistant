"""Test profile endpoints."""

import pytest


@pytest.mark.asyncio
async def test_get_profile_requires_auth(client):
    resp = await client.get("/api/profile")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_profile_requires_auth(client):
    resp = await client.put("/api/profile", json={"full_name": "Test"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_import_profile_requires_auth(client):
    resp = await client.post("/api/profile/import", json={"name": "Test"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_export_profile_requires_auth(client):
    resp = await client.get("/api/profile/export")
    assert resp.status_code == 401
