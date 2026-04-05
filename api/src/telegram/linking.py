"""Telegram account linking — code generation and verification."""

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models import NotificationPreference, TelegramAccount, TelegramLinkCode, User

logger = logging.getLogger(__name__)

LINK_CODE_LENGTH = 12
LINK_CODE_TTL_MINUTES = 10


async def generate_link_code(session: AsyncSession, user_id: str) -> dict:
    """Generate a one-time link code for Telegram account linking."""
    # Delete any existing codes for this user
    await session.execute(
        delete(TelegramLinkCode).where(TelegramLinkCode.user_id == uuid.UUID(user_id))
    )

    code = secrets.token_urlsafe(LINK_CODE_LENGTH)[:LINK_CODE_LENGTH]
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=LINK_CODE_TTL_MINUTES)

    link_code = TelegramLinkCode(
        user_id=uuid.UUID(user_id),
        code=code,
        expires_at=expires_at,
    )
    session.add(link_code)
    await session.commit()

    # Build deep link
    bot_username = ""
    if settings.telegram_bot_token:
        from src.telegram.sender import get_bot

        bot = get_bot()
        if bot:
            try:
                me = await bot.get_me()
                bot_username = me.username
            except Exception:
                logger.warning("Could not fetch bot username")

    deep_link = f"https://t.me/{bot_username}?start={code}" if bot_username else ""

    return {"code": code, "deep_link": deep_link}


async def verify_link_code(
    session: AsyncSession,
    code: str,
    chat_id: int,
    username: str | None,
) -> tuple[bool, str]:
    """Verify a link code from /start command. Returns (success, message)."""
    # Look up the code
    result = await session.execute(
        select(TelegramLinkCode).where(TelegramLinkCode.code == code)
    )
    link_code = result.scalar_one_or_none()

    if not link_code:
        return False, "Invalid or expired code. Please try again from Settings."

    if link_code.expires_at < datetime.now(timezone.utc):
        await session.delete(link_code)
        await session.commit()
        return False, "Code expired. Please generate a new one from Settings."

    # Get user to find tenant_id
    user_result = await session.execute(select(User).where(User.id == link_code.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        return False, "User not found."

    # Check if chat_id already linked to another account
    existing = await session.execute(
        select(TelegramAccount).where(TelegramAccount.chat_id == chat_id)
    )
    if existing.scalar_one_or_none():
        await session.delete(link_code)
        await session.commit()
        return False, "This Telegram account is already linked to another user."

    # Create telegram account
    telegram_account = TelegramAccount(
        tenant_id=user.tenant_id,
        user_id=user.id,
        chat_id=chat_id,
        username=username,
    )
    session.add(telegram_account)

    # Create default notification preferences (with tenant context)
    await session.execute(text(f"SET app.current_tenant = '{user.tenant_id}'"))

    existing_prefs = await session.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    if not existing_prefs.scalar_one_or_none():
        prefs = NotificationPreference(
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
        session.add(prefs)

    # Delete the used code
    await session.delete(link_code)
    await session.commit()

    return True, f"Linked to {user.email}! You'll now receive notifications here."


async def get_telegram_status(session: AsyncSession, user_id: str) -> dict:
    """Check if a user has a linked Telegram account."""
    result = await session.execute(
        select(TelegramAccount).where(TelegramAccount.user_id == uuid.UUID(user_id))
    )
    account = result.scalar_one_or_none()
    if account:
        return {
            "linked": True,
            "username": account.username,
            "chat_id": account.chat_id,
            "is_active": account.is_active,
        }
    return {"linked": False, "username": None, "chat_id": None, "is_active": False}


async def unlink_telegram(session: AsyncSession, user_id: str) -> bool:
    """Remove telegram account link."""
    result = await session.execute(
        select(TelegramAccount).where(TelegramAccount.user_id == uuid.UUID(user_id))
    )
    account = result.scalar_one_or_none()
    if account:
        await session.delete(account)
        await session.commit()
        return True
    return False
