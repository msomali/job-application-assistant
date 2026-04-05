"""Async PostgreSQL connection management with RLS tenant context."""

import logging
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None


def get_database_url() -> str:
    """Build database URL from DATABASE_URL env var or individual components."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    user = os.environ.get("POSTGRES_USER", "jobapp")
    password = os.environ.get("POSTGRES_PASSWORD", "jobapp_dev")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "jobapp")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


def get_engine():
    """Get or create the async SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_database_url(),
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """Set the RLS tenant context for the current database session."""
    if not tenant_id or tenant_id == "None":
        raise ValueError("tenant_id is required for RLS context")
    await session.execute(text(f"SET app.current_tenant = '{tenant_id}'"))


async def reset_engine() -> None:
    """Dispose the current engine. Used in tests and graceful shutdown."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
    _engine = None
    _session_factory = None
