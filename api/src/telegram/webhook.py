"""Telegram webhook + linking API routes."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.config import settings
from src.db.models import User
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import TelegramLinkCodeResponse, TelegramStatusResponse
from src.telegram.linking import (
    generate_link_code,
    get_telegram_status,
    unlink_telegram,
    verify_link_code,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook/{token}")
async def telegram_webhook(
    token: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Receive Telegram webhook updates."""
    if token != settings.telegram_bot_token:
        raise HTTPException(status_code=403, detail="Invalid token")

    body = await request.json()
    logger.info("Telegram webhook update: %s", json.dumps(body)[:200])

    # Handle /start command for account linking
    message = body.get("message", {})
    text = message.get("text", "")
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    from_user = message.get("from", {})
    username = from_user.get("username")

    if text.startswith("/start ") and chat_id:
        code = text.split(" ", 1)[1].strip()
        success, reply = await verify_link_code(session, code, chat_id, username)
        from src.telegram.sender import send_text
        await send_text(chat_id, reply)
        return {"ok": True}

    # Handle other commands
    if text.startswith("/") and chat_id:
        from src.telegram.handlers import handle_command
        await handle_command(session, chat_id, text, body)
        return {"ok": True}

    # Handle callback queries (inline keyboard buttons)
    callback_query = body.get("callback_query")
    if callback_query:
        cb_chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
        cb_data = callback_query.get("data", "")
        if cb_chat_id:
            from src.telegram.handlers import handle_callback
            await handle_callback(session, cb_chat_id, cb_data)
        return {"ok": True}

    return {"ok": True}


@router.post("/link-code", response_model=TelegramLinkCodeResponse)
async def create_link_code(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Generate a Telegram linking deep link for the current user."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=503, detail="Telegram bot not configured")
    result = await generate_link_code(session, str(user.id))
    return result


@router.get("/status", response_model=TelegramStatusResponse)
async def telegram_status(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Check if the current user has a linked Telegram account."""
    await set_tenant_context(session, str(user.tenant_id))
    return await get_telegram_status(session, str(user.id))


@router.delete("/unlink")
async def telegram_unlink(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Disconnect the current user's Telegram account."""
    await set_tenant_context(session, str(user.tenant_id))
    success = await unlink_telegram(session, str(user.id))
    if not success:
        raise HTTPException(status_code=404, detail="No linked Telegram account")
    return {"ok": True}
