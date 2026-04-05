"""Notification dispatcher — routes task events to Telegram."""

import logging
import uuid

from sqlalchemy import select

from src.config import settings
from src.db.models import NotificationPreference, TelegramAccount
from src.db.pg import get_session_factory, set_tenant_context
from src.notifications.formatters import format_task_event

logger = logging.getLogger(__name__)


async def notify(tenant_id: str, user_id: str | None, event_type: str, data: dict) -> None:
    """Dispatch a notification to Telegram if the user has it enabled.

    Fire-and-forget: catches all exceptions, logs, never blocks the caller.
    """
    if not settings.telegram_bot_token or not user_id:
        return

    try:
        factory = get_session_factory()
        async with factory() as session:
            await set_tenant_context(session, tenant_id)

            # Check notification preferences
            prefs_result = await session.execute(
                select(NotificationPreference).where(
                    NotificationPreference.user_id == uuid.UUID(user_id)
                )
            )
            prefs = prefs_result.scalar_one_or_none()

            # Default: telegram_enabled=True if no prefs row
            if prefs and not prefs.telegram_enabled:
                return

            # Get Telegram account
            acct_result = await session.execute(
                select(TelegramAccount).where(
                    TelegramAccount.user_id == uuid.UUID(user_id),
                    TelegramAccount.is_active == True,  # noqa: E712
                )
            )
            account = acct_result.scalar_one_or_none()
            if not account:
                return

            # Format and send
            text, buttons = format_task_event(event_type, data)
            if not text:
                return

            from src.telegram.sender import send_inline_keyboard, send_text

            if buttons:
                await send_inline_keyboard(account.chat_id, text, buttons)
            else:
                await send_text(account.chat_id, text)

    except Exception:
        logger.exception("Notification dispatch failed for user_id=%s event=%s", user_id, event_type)
