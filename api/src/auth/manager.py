"""User manager — handles registration, password hashing, tenant creation."""

import uuid

from fastapi import Request
from fastapi_users import BaseUserManager, UUIDIDMixin

from src.db.models import Tenant, User, UserProfile


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = "change-me"  # Overridden from settings at startup
    verification_token_secret = "change-me"

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        """After registration: create tenant + profile if user doesn't have one yet."""
        session = self.user_db.session

        if user.tenant_id is None:
            # New user — create a tenant for them
            tenant = Tenant(
                name=user.email.split("@")[0],
                slug=f"t-{uuid.uuid4().hex[:12]}",
            )
            session.add(tenant)
            await session.flush()
            user.tenant_id = tenant.id
            user.role = "owner"
            session.add(user)

        # Create empty profile
        profile = UserProfile(
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
        session.add(profile)
        await session.commit()
