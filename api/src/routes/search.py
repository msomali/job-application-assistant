"""Indeed + LinkedIn search endpoints."""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import Task as TaskModel
from src.db.models import User
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import TaskRead

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    location: str | None = None
    limit: int = 10


@router.post("/indeed", response_model=TaskRead, status_code=201)
async def search_indeed(
    request: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    task = TaskModel(
        tenant_id=user.tenant_id,
        type="search_indeed",
        input=request.model_dump(),
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    # Celery task wiring deferred until core search functions are adapted
    return task


@router.post("/linkedin", response_model=TaskRead, status_code=201)
async def search_linkedin(
    request: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    task = TaskModel(
        tenant_id=user.tenant_id,
        type="search_linkedin",
        input=request.model_dump(),
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task
