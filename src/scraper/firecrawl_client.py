"""Firecrawl client for scraping job postings."""

import json
import logging
import os
import re

import anthropic
from anthropic import APIError, APITimeoutError, RateLimitError
from firecrawl import FirecrawlApp

from src.models import JobPosting
from src.utils import retry

logger = logging.getLogger(__name__)

# Minimum signals to consider a page as a job posting
_JOB_SIGNALS = [
    "apply", "requirements", "responsibilities", "qualifications",
    "experience", "salary", "benefits", "job description",
    "we are looking for", "about the role", "what you'll do",
    "what you will do", "who you are", "about this role",
    "your responsibilities", "minimum qualifications", "preferred qualifications",
]


def _looks_like_job_page(markdown: str) -> bool:
    """Quick heuristic: does the page contain enough job-posting signals?"""
    sample = markdown[:4000].lower()
    matches = sum(1 for signal in _JOB_SIGNALS if signal in sample)
    return matches >= 2

EXTRACTION_MODEL = "claude-haiku-4-5-20251001"

EXTRACT_SYSTEM_PROMPT = """\
Extract all job posting details from the provided page content.
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

Return ONLY valid JSON, no markdown fences or extra text."""


def get_client() -> FirecrawlApp:
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise RuntimeError(
            "FIRECRAWL_API_KEY not set. Get one at https://www.firecrawl.dev/"
        )
    return FirecrawlApp(api_key=api_key)


@retry(max_retries=3, base_delay=1.0, max_delay=30.0, exceptions=(APIError, APITimeoutError, RateLimitError))
def _extract_with_claude(markdown: str) -> dict:
    """Use Claude to extract structured job data from markdown.

    Raises ValueError if the page doesn't look like a job posting.
    """
    if not _looks_like_job_page(markdown):
        raise ValueError("Page does not appear to be a job posting")

    # Cap input to avoid large token usage
    truncated = markdown[:12000]
    logger.debug("Extracting job data with Claude (markdown length: %d)", len(truncated))
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=EXTRACTION_MODEL,
        max_tokens=3000,
        system=[
            {
                "type": "text",
                "text": EXTRACT_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": truncated}],
    )
    logger.debug("Claude extraction complete")
    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    raw = re.sub(r"^\s*```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```\s*$", "", raw)
    data = json.loads(raw)

    # Validate required fields
    if not data.get("title") or not data.get("company"):
        raise ValueError(f"Missing required fields: title={data.get('title')}, company={data.get('company')}")

    return data


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
