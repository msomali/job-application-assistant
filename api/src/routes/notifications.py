"""Notification preference endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import NotificationPreference, User
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import NotificationPreferencesRead, NotificationPreferencesUpdate

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/preferences", response_model=NotificationPreferencesRead)
async def get_preferences(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    prefs = result.scalar_one_or_none()
    if prefs:
        return prefs
    return NotificationPreferencesRead()


@router.put("/preferences", response_model=NotificationPreferencesRead)
async def update_preferences(
    data: NotificationPreferencesUpdate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    prefs = result.scalar_one_or_none()
    if prefs:
        prefs.telegram_enabled = data.telegram_enabled
    else:
        prefs = NotificationPreference(
            tenant_id=user.tenant_id,
            user_id=user.id,
            telegram_enabled=data.telegram_enabled,
        )
        session.add(prefs)
    await session.commit()
    await session.refresh(prefs)
    return prefs
