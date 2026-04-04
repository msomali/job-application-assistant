"""FastAPI dependency injection — DB session, current user, tenant context."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User
from src.db.pg import get_session_factory, set_tenant_context


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session, closing it after the request."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def get_tenant_session(
    session: AsyncSession = Depends(get_db_session),
    user: "User" = Depends(lambda: None),  # Replaced by auth in routes
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a DB session with RLS tenant context set."""
    if user and user.tenant_id:
        await set_tenant_context(session, str(user.tenant_id))
    yield session
