"""fastapi-users SQLAlchemy adapter using our existing User model."""

from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User


class UserDatabase(SQLAlchemyUserDatabase):
    """Adapter that tells fastapi-users to use our User table."""
    pass


async def get_user_db(session: AsyncSession):
    yield UserDatabase(session, User)
