"""Test skills endpoints."""

import pytest


@pytest.mark.asyncio
async def test_top_skills_requires_auth(client):
    resp = await client.get("/api/skills/top")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_skill_gaps_requires_auth(client):
    resp = await client.get("/api/skills/gaps")
    assert resp.status_code == 401
