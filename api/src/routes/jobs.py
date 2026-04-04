"""Job endpoints — list, detail, scrape, analyze, generate, documents."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import Analysis, Application, Job, User
from src.db.models import Task as TaskModel
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import AnalysisRead, JobRead, JobScrapeRequest, TaskRead

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
async def list_jobs(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query("scraped_at", pattern="^(scraped_at|title|company)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    search: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    query = select(Job)
    if search:
        query = query.where(
            Job.title.ilike(f"%{search}%") | Job.company.ilike(f"%{search}%")
        )
    sort_col = getattr(Job, sort_by)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/ranked", response_model=list[JobRead])
async def ranked_jobs(
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Get jobs ranked by fit score (highest first)."""
    await set_tenant_context(session, str(user.tenant_id))
    query = (
        select(Job)
        .join(Analysis, Analysis.job_id == Job.id)
        .order_by(Analysis.fit_score.desc())
        .limit(limit)
    )
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await session.delete(job)
    await session.commit()


@router.post("/scrape", response_model=TaskRead, status_code=201)
async def scrape_job(
    request: JobScrapeRequest,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Enqueue a job scraping task."""
    await set_tenant_context(session, str(user.tenant_id))
    task = TaskModel(
        tenant_id=user.tenant_id,
        type="scrape",
        input={"url": str(request.url)},
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    from src.workers.tasks import scrape_job as scrape_task
    scrape_task.delay(str(task.id), str(user.tenant_id), str(request.url))

    return task


@router.get("/{job_id}/analysis", response_model=AnalysisRead)
async def get_analysis(
    job_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(Analysis).where(Analysis.job_id == job_id).order_by(Analysis.analyzed_at.desc())
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this job")
    return analysis


@router.post("/{job_id}/analyze", response_model=TaskRead, status_code=201)
async def analyze_job(
    job_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Enqueue a job analysis task."""
    await set_tenant_context(session, str(user.tenant_id))
    # Verify job exists
    result = await session.execute(select(Job).where(Job.id == job_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Job not found")

    task = TaskModel(
        tenant_id=user.tenant_id,
        type="analyze",
        input={"job_id": job_id},
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    from src.workers.tasks import analyze_job as analyze_task
    analyze_task.delay(str(task.id), str(user.tenant_id), job_id)

    return task


@router.post("/{job_id}/generate", response_model=TaskRead, status_code=201)
async def generate_docs(
    job_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Enqueue document generation task."""
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(Job).where(Job.id == job_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Job not found")

    task = TaskModel(
        tenant_id=user.tenant_id,
        type="generate",
        input={"job_id": job_id},
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    from src.workers.tasks import generate_docs as generate_task
    generate_task.delay(str(task.id), str(user.tenant_id), job_id)

    return task


@router.get("/{job_id}/documents")
async def get_documents(
    job_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Get pre-signed URLs for generated documents."""
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(Application).where(Application.job_id == job_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        return {"resume_url": None, "cover_letter_url": None}

    from src.storage import StorageClient
    storage = StorageClient()
    docs = {}
    if app.resume_path:
        docs["resume_url"] = storage.get_document_url(app.resume_path)
    if app.cover_letter_path:
        docs["cover_letter_url"] = storage.get_document_url(app.cover_letter_path)
    return docs
