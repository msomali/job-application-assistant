"""Test discovery and search endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_configs_requires_auth(client):
    resp = await client.get("/api/discovery/configs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_run_discovery_requires_auth(client):
    resp = await client.post("/api/discovery/run")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_indeed_requires_auth(client):
    resp = await client.post("/api/search/indeed", json={"query": "python developer"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_linkedin_requires_auth(client):
    resp = await client.post("/api/search/linkedin", json={"query": "python developer"})
    assert resp.status_code == 401
