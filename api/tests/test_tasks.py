"""Test task API endpoints."""

import uuid

import pytest


@pytest.mark.asyncio
async def test_list_tasks_requires_auth(client):
    resp = await client.get("/api/tasks")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_task_requires_auth(client):
    resp = await client.get(f"/api/tasks/{uuid.uuid4()}")
    assert resp.status_code == 401
