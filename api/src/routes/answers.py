"""Screening answer CRUD + import + stats."""

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import Answer, User
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import AnswerCreate, AnswerRead, AnswerUpdate

router = APIRouter(prefix="/api/answers", tags=["answers"])


def _hash_question(q: str) -> str:
    return hashlib.sha256(q.strip().lower().encode()).hexdigest()[:16]


@router.get("", response_model=list[AnswerRead])
async def list_answers(
    search: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    query = select(Answer)
    if search:
        query = query.where(Answer.question.ilike(f"%{search}%"))
    query = query.order_by(Answer.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


@router.post("", response_model=AnswerRead, status_code=201)
async def create_answer(
    data: AnswerCreate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    answer = Answer(
        tenant_id=user.tenant_id,
        question=data.question,
        question_hash=_hash_question(data.question),
        answer=data.answer,
        category=data.category,
    )
    session.add(answer)
    await session.commit()
    await session.refresh(answer)
    return answer


@router.put("/{answer_id}", response_model=AnswerRead)
async def update_answer(
    answer_id: int,
    data: AnswerUpdate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(Answer).where(Answer.id == answer_id))
    answer = result.scalar_one_or_none()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(answer, field, value)
    await session.commit()
    await session.refresh(answer)
    return answer


@router.delete("/{answer_id}", status_code=204)
async def delete_answer(
    answer_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(Answer).where(Answer.id == answer_id))
    answer = result.scalar_one_or_none()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    await session.delete(answer)
    await session.commit()


@router.post("/import", status_code=201)
async def import_answers(
    answers: list[dict],
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Bulk import answers from JSON."""
    await set_tenant_context(session, str(user.tenant_id))
    imported = 0
    for entry in answers:
        q = entry.get("question", "")
        a = entry.get("answer", "")
        if not q or not a:
            continue
        answer = Answer(
            tenant_id=user.tenant_id,
            question=q,
            question_hash=_hash_question(q),
            answer=a,
            category=entry.get("category"),
            source="import",
        )
        session.add(answer)
        imported += 1
    await session.commit()
    return {"imported": imported}


@router.get("/stats")
async def answer_stats(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    total = await session.execute(select(func.count(Answer.id)))
    used = await session.execute(select(func.count(Answer.id)).where(Answer.times_used > 0))
    return {
        "total": total.scalar(),
        "used": used.scalar(),
    }
