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
from src.config import get as cfg
from src.db.database import bulk_collect, init_db, save_analysis, save_job
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

    # Auto-collect jobs above threshold and send digest
    if new_jobs:
        min_score = cfg("scoring", "min_score_notify", 70)
        collectible = [j for j in new_jobs if j["fit_score"] >= min_score]
        if collectible:
            bulk_collect([j["id"] for j in collectible])
            logger.info("Auto-collected %d jobs with score >= %d", len(collectible), min_score)

        try:
            from src.agent.telegram_bot import send_notification

            digest_limit = cfg("telegram", "daily_digest_limit", 5)
            top = sorted(new_jobs, key=lambda j: j["fit_score"], reverse=True)[:digest_limit]
            lines = ["*Daily Job Digest:*\n"]
            for j in top:
                status = "collected" if j["fit_score"] >= min_score else "discovered"
                lines.append(
                    f"`{j['id']:>3}` | {j['fit_score']:>3}% | {status:<10} | "
                    f"{j['title'][:25]} @ {j['company'][:15]}"
                )
            lines.append(f"\n{len(new_jobs)} new, {len(collectible)} collected.")
            lines.append("Use /review to see collected jobs, /approve <ids> to generate docs.")
            await send_notification("\n".join(lines))
            logger.info("Telegram digest sent")
        except Exception as e:
            logger.exception("Could not send Telegram notification")
    else:
        logger.info("No new jobs found today")


if __name__ == "__main__":
    asyncio.run(main())
