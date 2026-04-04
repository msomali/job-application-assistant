"""User profile endpoints — CRUD + JSON import/export."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import User, UserProfile
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import ProfileRead, ProfileUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/profile", tags=["profile"])


async def _get_profile(session: AsyncSession, user: User) -> UserProfile:
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.get("", response_model=ProfileRead)
async def get_profile(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    return await _get_profile(session, user)


@router.put("", response_model=ProfileRead)
async def update_profile(
    data: ProfileUpdate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    profile = await _get_profile(session, user)
    update_data = data.model_dump(exclude_unset=True)
    # Convert nested models to dicts for JSONB/ARRAY storage
    if "contact" in update_data and update_data["contact"] is not None:
        update_data["contact"] = data.contact.model_dump()
    if "experience" in update_data and update_data["experience"] is not None:
        update_data["experience"] = [e.model_dump() for e in data.experience]
    if "education" in update_data and update_data["education"] is not None:
        update_data["education"] = [e.model_dump() for e in data.education]
    if "projects" in update_data and update_data["projects"] is not None:
        update_data["projects"] = [p.model_dump() for p in data.projects]

    for field, value in update_data.items():
        setattr(profile, field, value)
    await session.commit()
    await session.refresh(profile)
    return profile


@router.post("/import", response_model=ProfileRead)
async def import_profile(
    raw_json: dict,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Import a profile from master_resume.json format."""
    profile = await _get_profile(session, user)
    profile.raw_json = raw_json
    profile.full_name = raw_json.get("full_name") or raw_json.get("name")
    profile.contact = raw_json.get("contact", {})
    profile.summary = raw_json.get("summary")
    profile.experience = raw_json.get("experience", [])
    profile.education = raw_json.get("education", [])
    profile.skills = raw_json.get("skills", [])
    profile.certifications = raw_json.get("certifications", [])
    profile.projects = raw_json.get("projects", [])
    await session.commit()
    await session.refresh(profile)
    return profile


@router.get("/export")
async def export_profile(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Export profile as JSON (master_resume.json format)."""
    profile = await _get_profile(session, user)
    if profile.raw_json:
        return profile.raw_json
    return {
        "full_name": profile.full_name,
        "contact": profile.contact,
        "summary": profile.summary,
        "experience": profile.experience,
        "education": profile.education,
        "skills": profile.skills,
        "certifications": profile.certifications,
        "projects": profile.projects,
    }
