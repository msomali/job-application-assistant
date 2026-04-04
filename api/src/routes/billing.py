"""Billing endpoints — plan, usage, history (stubs until Stripe)."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import ApiUsageLog, Tenant, User
from src.db.pg import set_tenant_context
from src.deps import get_db_session

router = APIRouter(prefix="/api/billing", tags=["billing"])

PLAN_LIMITS = {
    "free": {"scrapes_per_day": 10, "analyses_per_day": 20, "generations_per_day": 5},
    "pro": {"scrapes_per_day": 100, "analyses_per_day": 200, "generations_per_day": 50},
    "enterprise": {"scrapes_per_day": 1000, "analyses_per_day": 2000, "generations_per_day": 500},
}


@router.get("/plan")
async def get_plan(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one()
    limits = PLAN_LIMITS.get(tenant.plan, PLAN_LIMITS["free"])
    return {"plan": tenant.plan, "limits": limits}


@router.get("/usage")
async def get_usage(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await session.execute(
        select(ApiUsageLog.action, func.count(ApiUsageLog.id), func.sum(ApiUsageLog.tokens_used))
        .where(ApiUsageLog.created_at >= period_start)
        .group_by(ApiUsageLog.action)
    )
    usage = {}
    total_tokens = 0
    for action, count, tokens in result.all():
        usage[action] = count
        total_tokens += tokens or 0

    return {
        "period_start": period_start.isoformat(),
        "period_end": now.isoformat(),
        "actions": usage,
        "tokens_used": total_tokens,
    }


@router.get("/usage/history")
async def usage_history(
    days: int = 30,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await session.execute(
        select(
            func.date_trunc("day", ApiUsageLog.created_at).label("day"),
            ApiUsageLog.action,
            func.count(ApiUsageLog.id).label("count"),
        )
        .where(ApiUsageLog.created_at >= since)
        .group_by("day", ApiUsageLog.action)
        .order_by("day")
    )
    return [{"day": str(row[0]), "action": row[1], "count": row[2]} for row in result.all()]


@router.get("/invoices")
async def list_invoices(user: User = Depends(current_active_user)):
    """Stub — returns empty list until Stripe integration."""
    return []
