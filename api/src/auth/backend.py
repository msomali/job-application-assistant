"""JWT authentication backend for fastapi-users."""

import uuid

from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.manager import UserManager
from src.auth.models import get_user_db
from src.config import settings
from src.db.models import User
from src.deps import get_db_session


bearer_transport = BearerTransport(tokenUrl="/api/auth/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.jwt_secret, lifetime_seconds=settings.jwt_lifetime_seconds)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)


async def get_user_manager(session: AsyncSession = Depends(get_db_session)):
    user_db = get_user_db(session)
    # get_user_db is an async generator — need to advance it
    db = await user_db.__anext__()
    yield UserManager(db)


fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
