"""FastAPI dependency injection — DB session, current user, tenant context."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.pg import get_session_factory, set_tenant_context


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session, closing it after the request."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def get_tenant_session(
    tenant_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a DB session with RLS tenant context set."""
    await set_tenant_context(session, tenant_id)
    yield session
