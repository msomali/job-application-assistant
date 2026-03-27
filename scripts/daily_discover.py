"""Daily job discovery script triggered by cron.

Discovers new jobs, analyzes them, and sends a Telegram digest.
"""

import asyncio
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from src.logging_config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

from src.analyzer.job_analyzer import analyze_job
from src.db.database import init_db, list_jobs, save_analysis, save_job
from src.models import JobPosting
from src.scraper.firecrawl_client import _extract_with_claude
from src.scraper.job_discovery import discover_all


async def main():
    init_db()

    logger.info("Starting daily job discovery...")
    results = discover_all()
    logger.info("Discovered %d unique job pages", len(results))

    new_jobs = []
    for result in results:
        url = result["url"]
        markdown = result.get("markdown", "")

        if not markdown.strip():
            continue

        try:
            extracted = _extract_with_claude(markdown)
            job = JobPosting(**extracted)
        except Exception as e:
            logger.debug("Skipping non-job page %s: %s", url, e)
            continue

        job_id = save_job(job.model_dump(), url, markdown)
        analysis = analyze_job(job)
        save_analysis(job_id, analysis.model_dump())

        new_jobs.append({
            "id": job_id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "fit_score": analysis.fit_score,
        })
        logger.info("[%d] %s at %s - Score: %d", job_id, job.title, job.company, analysis.fit_score)

    # Send Telegram digest
    if new_jobs:
        try:
            from src.agent.telegram_bot import send_notification

            top = sorted(new_jobs, key=lambda j: j["fit_score"], reverse=True)[:5]
            lines = ["*Daily Job Digest:*\n"]
            for j in top:
                lines.append(
                    f"`{j['id']:>3}` | {j['fit_score']:>3}% | {j['title'][:25]} @ {j['company'][:15]} ({j['location'][:15]})"
                )
            lines.append(f"\n{len(new_jobs)} new jobs found. Use /job <id> for details.")
            await send_notification("\n".join(lines))
            logger.info("Telegram digest sent")
        except Exception as e:
            logger.exception("Could not send Telegram notification")
    else:
        logger.info("No new jobs found today")


if __name__ == "__main__":
    asyncio.run(main())
