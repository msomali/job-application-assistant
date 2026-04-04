"""Tests for PostgreSQL async connection module."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from src.db.pg import get_database_url, set_tenant_context


def test_get_database_url_from_env():
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/testdb"}):
        url = get_database_url()
        assert "postgresql+asyncpg" in url
        assert "testdb" in url


def test_get_database_url_from_components():
    env = {
        "POSTGRES_USER": "myuser",
        "POSTGRES_PASSWORD": "mypass",
        "POSTGRES_HOST": "dbhost",
        "POSTGRES_PORT": "5433",
        "POSTGRES_DB": "mydb",
    }
    with patch.dict(os.environ, env, clear=False):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DATABASE_URL", None)
            url = get_database_url()
            assert url == "postgresql+asyncpg://myuser:mypass@dbhost:5433/mydb"


@pytest.mark.asyncio
async def test_set_tenant_context():
    mock_session = AsyncMock()
    tenant_id = "550e8400-e29b-41d4-a716-446655440000"
    await set_tenant_context(mock_session, tenant_id)
    mock_session.execute.assert_called_once()
    # Extract the TextClause argument and check its SQL text
    args = mock_session.execute.call_args
    text_clause = args[0][0]
    assert "app.current_tenant" in text_clause.text
    assert tenant_id in text_clause.text
