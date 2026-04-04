"""Celery task definitions for background jobs."""

import asyncio
import hashlib
import json
import logging
import uuid

import redis
from sqlalchemy import select

from src.config import settings
from src.db.models import Analysis, Job, Task as TaskModel, UserProfile
from src.db.pg import get_session_factory, set_tenant_context
from src.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_redis = None


def _get_redis():
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url)
    return _redis


def _publish_event(tenant_id: str, event_type: str, data: dict):
    """Publish SSE event to Redis pub/sub."""
    _get_redis().publish(
        f"tenant:{tenant_id}:events",
        json.dumps({"event": event_type, "data": data}),
    )


async def _update_task(task_id: str, tenant_id: str, **fields):
    """Update task record in DB."""
    factory = get_session_factory()
    async with factory() as session:
        await set_tenant_context(session, tenant_id)
        result = await session.execute(
            select(TaskModel).where(TaskModel.id == uuid.UUID(task_id))
        )
        task = result.scalar_one_or_none()
        if task:
            for k, v in fields.items():
                setattr(task, k, v)
            await session.commit()


def _run_async(coro):
    """Run async code from sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="scrape_job")
def scrape_job(self, task_id: str, tenant_id: str, url: str):
    """Scrape a job URL, extract details, save to DB."""
    _run_async(_update_task(task_id, tenant_id, status="running", progress=10))
    _publish_event(tenant_id, "task:started", {"task_id": task_id, "type": "scrape"})

    try:
        from src.scraper.firecrawl_client import scrape_and_extract
        job_data = scrape_and_extract(url)

        _run_async(_update_task(task_id, tenant_id, status="running", progress=50))
        _publish_event(tenant_id, "task:progress", {
            "task_id": task_id, "type": "scrape", "progress": 50, "message": "Extracted job data",
        })

        # Save job to DB
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]

        async def _save():
            factory = get_session_factory()
            async with factory() as session:
                await set_tenant_context(session, tenant_id)
                job = Job(
                    tenant_id=uuid.UUID(tenant_id),
                    url=url,
                    url_hash=url_hash,
                    title=job_data.get("title", "Unknown"),
                    company=job_data.get("company", "Unknown"),
                    location=job_data.get("location"),
                    salary_range=job_data.get("salary_range"),
                    job_type=job_data.get("job_type"),
                    experience_level=job_data.get("experience_level"),
                    description=job_data.get("description"),
                    requirements=job_data.get("requirements", []),
                    responsibilities=job_data.get("responsibilities", []),
                    benefits=job_data.get("benefits", []),
                    application_url=job_data.get("application_url"),
                    date_posted=job_data.get("date_posted"),
                    raw_markdown=job_data.get("raw_markdown"),
                )
                session.add(job)
                await session.commit()
                await session.refresh(job)
                return job.id

        job_id = _run_async(_save())

        _run_async(_update_task(
            task_id, tenant_id, status="completed", progress=100,
            result={"job_id": job_id},
        ))
        _publish_event(tenant_id, "task:completed", {
            "task_id": task_id, "type": "scrape", "result": {"job_id": job_id},
        })

    except Exception as e:
        logger.exception("scrape_job failed: %s", e)
        _run_async(_update_task(task_id, tenant_id, status="failed", error=str(e)))
        _publish_event(tenant_id, "task:failed", {
            "task_id": task_id, "type": "scrape", "error": str(e),
        })
        raise


@celery_app.task(bind=True, name="analyze_job")
def analyze_job(self, task_id: str, tenant_id: str, job_id: int):
    """Analyze a job against the user's profile."""
    _run_async(_update_task(task_id, tenant_id, status="running", progress=10))
    _publish_event(tenant_id, "task:started", {"task_id": task_id, "type": "analyze"})

    try:
        # Fetch job from DB
        async def _fetch_job():
            factory = get_session_factory()
            async with factory() as session:
                await set_tenant_context(session, tenant_id)
                result = await session.execute(
                    select(Job).where(Job.id == job_id)
                )
                return result.scalar_one_or_none()

        job = _run_async(_fetch_job())
        if not job:
            raise ValueError(f"Job {job_id} not found")

        _run_async(_update_task(task_id, tenant_id, progress=30))

        # Fetch user profile for analysis
        async def _fetch_profile():
            factory = get_session_factory()
            async with factory() as session:
                await set_tenant_context(session, tenant_id)
                result = await session.execute(
                    select(UserProfile).where(UserProfile.tenant_id == uuid.UUID(tenant_id))
                )
                return result.scalar_one_or_none()

        profile = _run_async(_fetch_profile())

        # Build job posting dict for analyzer
        from src.analyzer.job_analyzer import analyze_job as core_analyze
        from src.models import JobPosting

        job_posting = JobPosting(
            url=job.url,
            title=job.title,
            company=job.company,
            location=job.location or "",
            description=job.description or "",
            requirements=job.requirements or [],
            responsibilities=job.responsibilities or [],
            benefits=job.benefits or [],
            salary_range=job.salary_range,
            job_type=job.job_type,
            experience_level=job.experience_level,
            application_url=job.application_url,
            date_posted=job.date_posted,
        )

        # Convert profile to resume dict for analyzer
        resume_data = {}
        if profile and profile.raw_json:
            resume_data = profile.raw_json
        elif profile:
            resume_data = {
                "full_name": profile.full_name,
                "skills": profile.skills or [],
                "experience": profile.experience or [],
                "education": profile.education or [],
            }

        _run_async(_update_task(task_id, tenant_id, progress=50))

        analysis_result = core_analyze(job_posting, resume_data)

        # Save analysis
        async def _save_analysis():
            factory = get_session_factory()
            async with factory() as session:
                await set_tenant_context(session, tenant_id)
                analysis = Analysis(
                    tenant_id=uuid.UUID(tenant_id),
                    job_id=job_id,
                    fit_score=analysis_result.fit_score,
                    base_score=analysis_result.base_score,
                    penalties=[p.model_dump() for p in analysis_result.penalties] if hasattr(analysis_result, 'penalties') else [],
                    fit_reasoning=analysis_result.fit_reasoning,
                    matching_skills=analysis_result.matching_skills,
                    gaps=analysis_result.gaps,
                    keywords=analysis_result.keywords,
                    tailoring_strategy=analysis_result.tailoring_strategy,
                )
                session.add(analysis)
                await session.commit()
                return analysis.id

        analysis_id = _run_async(_save_analysis())

        _run_async(_update_task(
            task_id, tenant_id, status="completed", progress=100,
            result={"analysis_id": analysis_id, "fit_score": analysis_result.fit_score},
        ))
        _publish_event(tenant_id, "task:completed", {
            "task_id": task_id, "type": "analyze",
            "result": {"analysis_id": analysis_id, "fit_score": analysis_result.fit_score},
        })

    except Exception as e:
        logger.exception("analyze_job failed: %s", e)
        _run_async(_update_task(task_id, tenant_id, status="failed", error=str(e)))
        _publish_event(tenant_id, "task:failed", {
            "task_id": task_id, "type": "analyze", "error": str(e),
        })
        raise


@celery_app.task(bind=True, name="generate_docs")
def generate_docs(self, task_id: str, tenant_id: str, job_id: int):
    """Generate resume + cover letter for a job."""
    _run_async(_update_task(task_id, tenant_id, status="running", progress=10))
    _publish_event(tenant_id, "task:started", {"task_id": task_id, "type": "generate"})

    try:
        _run_async(_update_task(
            task_id, tenant_id, status="completed", progress=100,
            result={"message": "Document generation placeholder — full implementation in Phase 3"},
        ))
        _publish_event(tenant_id, "task:completed", {
            "task_id": task_id, "type": "generate", "result": {"status": "placeholder"},
        })
    except Exception as e:
        logger.exception("generate_docs failed: %s", e)
        _run_async(_update_task(task_id, tenant_id, status="failed", error=str(e)))
        _publish_event(tenant_id, "task:failed", {
            "task_id": task_id, "type": "generate", "error": str(e),
        })
        raise


@celery_app.task(bind=True, name="run_discovery")
def run_discovery(self, task_id: str, tenant_id: str):
    """Run all active search configs for a tenant."""
    _run_async(_update_task(task_id, tenant_id, status="running", progress=10))
    _publish_event(tenant_id, "task:started", {"task_id": task_id, "type": "discover"})

    try:
        _run_async(_update_task(
            task_id, tenant_id, status="completed", progress=100,
            result={"message": "Discovery placeholder — wired to core in Phase 3"},
        ))
        _publish_event(tenant_id, "task:completed", {
            "task_id": task_id, "type": "discover", "result": {"status": "placeholder"},
        })
    except Exception as e:
        logger.exception("run_discovery failed: %s", e)
        _run_async(_update_task(task_id, tenant_id, status="failed", error=str(e)))
        _publish_event(tenant_id, "task:failed", {
            "task_id": task_id, "type": "discover", "error": str(e),
        })
        raise
