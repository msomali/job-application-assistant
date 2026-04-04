"""Discovery endpoints — search config CRUD and run."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import SearchConfig, User
from src.db.models import Task as TaskModel
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import SearchConfigCreate, SearchConfigRead, SearchConfigUpdate, TaskRead

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/discovery", tags=["discovery"])


@router.get("/configs", response_model=list[SearchConfigRead])
async def list_configs(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(SearchConfig).order_by(SearchConfig.created_at.desc()))
    return result.scalars().all()


@router.post("/configs", response_model=SearchConfigRead, status_code=201)
async def create_config(
    data: SearchConfigCreate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    config = SearchConfig(
        tenant_id=user.tenant_id,
        name=data.name,
        config_type=data.config_type,
        config=data.config,
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config


@router.put("/configs/{config_id}", response_model=SearchConfigRead)
async def update_config(
    config_id: int,
    data: SearchConfigUpdate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(SearchConfig).where(SearchConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(config, field, value)
    await session.commit()
    await session.refresh(config)
    return config


@router.delete("/configs/{config_id}", status_code=204)
async def delete_config(
    config_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(SearchConfig).where(SearchConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    await session.delete(config)
    await session.commit()


@router.post("/run", response_model=TaskRead, status_code=201)
async def run_discovery(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Run all active search configs."""
    await set_tenant_context(session, str(user.tenant_id))
    task = TaskModel(
        tenant_id=user.tenant_id,
        type="discover",
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    from src.workers.tasks import run_discovery as discovery_task
    discovery_task.delay(str(task.id), str(user.tenant_id))

    return task
