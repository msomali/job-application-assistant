"""Test billing endpoints."""

import pytest


@pytest.mark.asyncio
async def test_get_plan_requires_auth(client):
    resp = await client.get("/api/billing/plan")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_usage_requires_auth(client):
    resp = await client.get("/api/billing/usage")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invoices_requires_auth(client):
    resp = await client.get("/api/billing/invoices")
    assert resp.status_code == 401
