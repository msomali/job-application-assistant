"""Test answers endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_answers_requires_auth(client):
    resp = await client.get("/api/answers")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_answer_requires_auth(client):
    resp = await client.post("/api/answers", json={"question": "Q", "answer": "A"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_answer_stats_requires_auth(client):
    resp = await client.get("/api/answers/stats")
    assert resp.status_code == 401
