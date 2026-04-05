"""JWT authentication backend for fastapi-users — access + refresh tokens."""

import uuid

from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
    JWTStrategy,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.manager import UserManager
from src.auth.models import get_user_db
from src.config import settings
from src.db.models import User
from src.deps import get_db_session

# --- Access token (Bearer header, 15 min) ---
bearer_transport = BearerTransport(tokenUrl="/api/auth/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.jwt_secret, lifetime_seconds=settings.jwt_lifetime_seconds)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# --- Refresh token (httpOnly cookie, 7 days) ---
cookie_transport = CookieTransport(
    cookie_name="refresh_token",
    cookie_httponly=True,
    cookie_secure=settings.cookie_secure,
    cookie_samesite="lax",
    cookie_max_age=settings.jwt_refresh_lifetime_seconds,
)


def get_refresh_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.jwt_secret,
        lifetime_seconds=settings.jwt_refresh_lifetime_seconds,
        token_audience=["fastapi-users:refresh"],
    )


refresh_backend = AuthenticationBackend(
    name="jwt-refresh",
    transport=cookie_transport,
    get_strategy=get_refresh_strategy,
)


# --- User manager dependency ---
async def get_user_manager(session: AsyncSession = Depends(get_db_session)):
    user_db = get_user_db(session)
    db = await user_db.__anext__()
    yield UserManager(db)


# --- FastAPI Users instance ---
fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend, refresh_backend])

current_active_user = fastapi_users.current_user(active=True)
