"""Firecrawl client for scraping job postings."""

import json
import logging
import os

import anthropic
from anthropic import APIError, APITimeoutError, RateLimitError
from firecrawl import FirecrawlApp

from src.models import JobPosting
from src.utils import retry

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """\
Extract all job posting details from the following page content.
Return a JSON object with exactly these fields:

- "title": job title (string, required)
- "company": company name (string, required)
- "location": job location (string, required)
- "salary_range": salary range if mentioned (string or null)
- "job_type": full-time/part-time/contract (string or null)
- "experience_level": entry/mid/senior/staff/principal (string or null)
- "description": full job description (string, required)
- "requirements": list of requirement strings
- "responsibilities": list of responsibility strings
- "benefits": list of benefit strings
- "application_url": direct application URL if found (string or null)
- "date_posted": posting date if found (string or null)

Return ONLY valid JSON, no markdown fences or extra text.

Page content:
{markdown}
"""


def get_client() -> FirecrawlApp:
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise RuntimeError(
            "FIRECRAWL_API_KEY not set. Get one at https://www.firecrawl.dev/"
        )
    return FirecrawlApp(api_key=api_key)


@retry(max_retries=3, base_delay=1.0, max_delay=30.0, exceptions=(APIError, APITimeoutError, RateLimitError))
def _extract_with_claude(markdown: str) -> dict:
    """Use Claude to extract structured job data from markdown."""
    logger.debug("Extracting job data with Claude (markdown length: %d)", len(markdown))
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        messages=[
            {"role": "user", "content": EXTRACT_PROMPT.format(markdown=markdown)}
        ],
    )
    logger.debug("Claude extraction complete")
    return json.loads(message.content[0].text)


@retry(max_retries=3, base_delay=1.0, max_delay=30.0, exceptions=(Exception,))
def scrape_job(url: str) -> tuple[JobPosting, str]:
    """Scrape a single job posting URL.

    Returns (structured JobPosting, raw markdown).
    """
    logger.info("Scraping job URL: %s", url)
    app = get_client()

    doc = app.scrape(
        url=url,
        formats=["markdown"],
        only_main_content=True,
        wait_for=3000,
    )

    raw_markdown = doc.markdown or ""

    if not raw_markdown.strip():
        logger.warning("No content scraped from %s", url)
        raise RuntimeError(f"No content scraped from {url}")

    extracted = _extract_with_claude(raw_markdown)
    job = JobPosting(**extracted)

    if not job.application_url:
        job.application_url = url

    logger.info("Successfully scraped job: %s at %s", job.title, job.company)
    return job, raw_markdown


def scrape_job_with_scroll(url: str) -> tuple[JobPosting, str]:
    """Scrape a job page that requires scrolling to load full content."""
    logger.info("Scraping job URL with scroll: %s", url)
    app = get_client()

    doc = app.scrape(
        url=url,
        formats=["markdown"],
        only_main_content=True,
        actions=[
            {"type": "scroll", "direction": "down", "amount": 3},
            {"type": "wait", "milliseconds": 2000},
            {"type": "scroll", "direction": "down", "amount": 3},
            {"type": "wait", "milliseconds": 1000},
            {"type": "scrape"},
        ],
    )

    raw_markdown = doc.markdown or ""

    if not raw_markdown.strip():
        raise RuntimeError(f"No content scraped from {url}")

    extracted = _extract_with_claude(raw_markdown)
    job = JobPosting(**extracted)

    if not job.application_url:
        job.application_url = url

    return job, raw_markdown
