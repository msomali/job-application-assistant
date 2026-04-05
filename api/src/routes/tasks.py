"""Task status and SSE streaming endpoints."""

import json
import logging
import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from src.auth.backend import current_active_user, get_jwt_strategy, get_user_manager
from src.config import settings
from src.db.models import Task as TaskModel
from src.db.models import User
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import TaskRead

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# --- SSE stream must be defined BEFORE /{task_id} to avoid route conflict ---
@router.get("/stream")
async def task_stream(
    token: str = Query(...),
    user_manager: "UserManager" = Depends(get_user_manager),
):
    """SSE endpoint — streams task events for the current tenant.

    Uses query-param token because EventSource cannot set headers.
    """
    strategy = get_jwt_strategy()
    user = await strategy.read_token(token, user_manager)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    tenant_id = str(user.tenant_id)

    async def event_generator():
        r = aioredis.from_url(settings.redis_url)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"tenant:{tenant_id}:events")
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30)
                if message and message["type"] == "message":
                    data = json.loads(message["data"])
                    yield {"event": data["event"], "data": json.dumps(data["data"])}
                else:
                    # Send keepalive
                    yield {"event": "ping", "data": ""}
        finally:
            await pubsub.unsubscribe(f"tenant:{tenant_id}:events")
            await r.aclose()

    return EventSourceResponse(event_generator())


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    limit: int = 20,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(TaskModel).order_by(TaskModel.created_at.desc()).limit(limit)
    )
    return result.scalars().all()


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(TaskModel).where(TaskModel.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
