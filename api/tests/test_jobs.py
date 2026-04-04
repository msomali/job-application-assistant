"""Test job endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_jobs_requires_auth(client):
    resp = await client.get("/api/jobs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_job_requires_auth(client):
    resp = await client.get("/api/jobs/1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_scrape_job_requires_auth(client):
    resp = await client.post("/api/jobs/scrape", json={"url": "https://example.com/job"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ranked_jobs_requires_auth(client):
    resp = await client.get("/api/jobs/ranked")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_job_requires_auth(client):
    resp = await client.delete("/api/jobs/1")
    assert resp.status_code == 401
