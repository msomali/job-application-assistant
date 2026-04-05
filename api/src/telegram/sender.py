"""Outbound Telegram messages — text, inline keyboards, documents."""

import logging

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config import settings

logger = logging.getLogger(__name__)

_bot: telegram.Bot | None = None


def get_bot() -> telegram.Bot | None:
    """Lazy-init the Telegram bot. Returns None if token not configured."""
    global _bot
    if not settings.telegram_bot_token:
        return None
    if _bot is None:
        _bot = telegram.Bot(token=settings.telegram_bot_token)
    return _bot


async def send_text(chat_id: int, text: str, parse_mode: str = "Markdown") -> None:
    """Send a text message to a Telegram chat."""
    bot = get_bot()
    if not bot:
        return
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
    except Exception:
        logger.exception("Failed to send Telegram message to chat_id=%s", chat_id)


async def send_inline_keyboard(
    chat_id: int,
    text: str,
    buttons: list[list[tuple[str, str]]],
    parse_mode: str = "Markdown",
) -> None:
    """Send a message with inline keyboard buttons.

    buttons: list of rows, each row is a list of (label, callback_data) tuples.
    """
    bot = get_bot()
    if not bot:
        return
    keyboard = [
        [InlineKeyboardButton(label, callback_data=data) for label, data in row]
        for row in buttons
    ]
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception:
        logger.exception("Failed to send Telegram keyboard to chat_id=%s", chat_id)


async def send_document(chat_id: int, document: bytes, filename: str, caption: str = "") -> None:
    """Send a file (e.g., PDF) to a Telegram chat."""
    bot = get_bot()
    if not bot:
        return
    try:
        await bot.send_document(
            chat_id=chat_id,
            document=document,
            filename=filename,
            caption=caption,
        )
    except Exception:
        logger.exception("Failed to send Telegram document to chat_id=%s", chat_id)
