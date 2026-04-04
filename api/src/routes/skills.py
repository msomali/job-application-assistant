"""Skill analytics endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import Job, JobSkill, User, UserProfile
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import SkillCount, SkillGap

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("/top", response_model=list[SkillCount])
async def top_skills(
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(JobSkill.skill, func.count(JobSkill.id).label("count"))
        .group_by(JobSkill.skill)
        .order_by(func.count(JobSkill.id).desc())
        .limit(limit)
    )
    return [SkillCount(skill=row[0], count=row[1]) for row in result.all()]


@router.get("/gaps", response_model=list[SkillGap])
async def skill_gaps(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    # Get user's skills
    profile_result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    profile = profile_result.scalar_one_or_none()
    user_skills = set(s.lower() for s in (profile.skills or [])) if profile else set()

    # Get demanded skills
    result = await session.execute(
        select(JobSkill.skill, func.count(JobSkill.id).label("count"))
        .group_by(JobSkill.skill)
        .order_by(func.count(JobSkill.id).desc())
    )
    gaps = []
    for skill, count in result.all():
        if skill.lower() not in user_skills:
            gaps.append(SkillGap(skill=skill, demand_count=count))
    return gaps[:30]


@router.get("/trends")
async def skill_trends(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Skill demand over time — returns raw data for frontend charting."""
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(
            func.date_trunc("week", JobSkill.extracted_at).label("week"),
            JobSkill.skill,
            func.count(JobSkill.id).label("count"),
        )
        .group_by("week", JobSkill.skill)
        .order_by("week")
    )
    return [{"week": str(row[0]), "skill": row[1], "count": row[2]} for row in result.all()]


@router.get("/roles")
async def skills_by_role(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Skills grouped by job experience level."""
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(Job.experience_level, JobSkill.skill, func.count(JobSkill.id).label("count"))
        .join(JobSkill, JobSkill.job_id == Job.id)
        .where(Job.experience_level.isnot(None))
        .group_by(Job.experience_level, JobSkill.skill)
        .order_by(Job.experience_level, func.count(JobSkill.id).desc())
    )
    roles = {}
    for level, skill, count in result.all():
        roles.setdefault(level, []).append({"skill": skill, "count": count})
    return roles
