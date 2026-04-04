"""Shared test fixtures for API tests."""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.app import create_app
from src.deps import get_db_session


class MockResult:
    """Mock SQLAlchemy result that supports scalar_one_or_none etc."""

    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalar_one(self):
        return self._value

    def scalar(self):
        return self._value

    def unique(self):
        return self

    def scalars(self):
        return self

    def all(self):
        return []

    def first(self):
        return self._value


@pytest.fixture
def mock_session():
    """Mock async DB session."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MockResult(None))
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.close = AsyncMock()
    session.refresh = AsyncMock()
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
