"""Tenant admin endpoints — user management."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import User
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import UserRead

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(user: User):
    if user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/users", response_model=list[UserRead])
async def list_users(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    _require_admin(user)
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(User).where(User.tenant_id == user.tenant_id)
    )
    return result.scalars().all()


@router.put("/users/{user_id}/role")
async def change_role(
    user_id: str,
    role: str,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    _require_admin(user)
    if role not in ("owner", "admin", "member"):
        raise HTTPException(status_code=400, detail="Invalid role")
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.role = role
    await session.commit()
    return {"status": "ok", "user_id": user_id, "role": role}


@router.delete("/users/{user_id}", status_code=204)
async def remove_user(
    user_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    _require_admin(user)
    await set_tenant_context(session, str(user.tenant_id))
    if uuid.UUID(user_id) == user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_active = False
    await session.commit()
