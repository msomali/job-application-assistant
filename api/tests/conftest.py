"""Shared test fixtures for API tests."""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.app import create_app
from src.deps import get_db_session


@pytest.fixture
def mock_session():
    """Mock async DB session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def app(mock_session):
    """Create test app with mocked DB."""
    test_app = create_app()

    async def override_get_db():
        yield mock_session

    test_app.dependency_overrides[get_db_session] = override_get_db
    return test_app


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def tenant_id() -> str:
    return str(uuid.uuid4())
