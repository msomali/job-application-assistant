"""Job discovery via Firecrawl search and company career page crawling."""

import json
import logging
import os
from pathlib import Path

import click
from firecrawl import FirecrawlApp

from src.config import get as cfg
from src.utils import retry

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent.parent / "data" / "search_config.json"

# Job board aggregator URLs we should skip (they list jobs, not individual postings)
SKIP_DOMAINS = set(cfg("discovery", "skip_domains", [
    "linkedin.com", "indeed.com", "glassdoor.com", "ziprecruiter.com",
]))

# Non-job domains: informational sites that search engines return for role queries
NON_JOB_DOMAINS = {
    "youtube.com", "wikipedia.org", "coursera.org", "medium.com",
    "reddit.com", "quora.com", "stackoverflow.com", "github.com",
    "twitter.com", "x.com", "facebook.com", "udemy.com", "edx.org",
    "kaggle.com", "towardsdatascience.com", "geeksforgeeks.org",
    "w3schools.com", "codecademy.com", "pluralsight.com", "wgu.edu",
    "snhu.edu", "bls.gov", "computerscience.org", "theforage.com",
    "roadmap.sh", "ibm.com", "dataanalyst.com", "northeastern.edu",
    "seas.harvard.edu", "ischool.syracuse.edu", "ucr.edu",
    "databricks.com", "getdbt.com", "distantjob.com",
    "builtinsf.com", "builtin.com",
}


def get_client() -> FirecrawlApp:
    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise RuntimeError(
            "FIRECRAWL_API_KEY not set. Get one at https://www.firecrawl.dev/"
        )
    return FirecrawlApp(api_key=api_key)


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Search config not found at {CONFIG_PATH}")
    return json.loads(CONFIG_PATH.read_text())


def _should_skip_url(url: str) -> bool:
    """Skip aggregator sites, informational pages, and unsupported domains."""
    from urllib.parse import urlparse

    from src.scraper.browser_session import has_session

    domain = urlparse(url).netloc.lower()

    # LinkedIn/Indeed: only skip if we don't have a saved session
    if "linkedin.com" in domain:
        if has_session("linkedin"):
            return False
        logger.debug("Skipping LinkedIn URL (no session): %s", url)
        return True
    if "indeed.com" in domain:
        if has_session("indeed"):
            return False
        logger.debug("Skipping Indeed URL (no session): %s", url)
        return True

    # Skip job board aggregators
    if any(skip in domain for skip in SKIP_DOMAINS):
        return True

    # Skip informational/educational sites (not job postings)
    if any(non_job in domain for non_job in NON_JOB_DOMAINS):
        logger.debug("Skipping non-job domain: %s", url)
        return True

    return False


@retry(max_retries=3, base_delay=1.0, max_delay=30.0, exceptions=(Exception,))
def search_jobs(query: str, limit: int = 5) -> list[dict]:
    """Search the web for job listings matching a query.

    Returns a list of dicts with 'url', 'title', and 'description'.
    Search results don't include markdown, so pages need to be scraped separately.
    """
    logger.info("Searching for jobs: %s (limit=%d)", query, limit)
    app = get_client()
    result = app.search(query=query, limit=limit)

    jobs = []
    items = result.web if hasattr(result, "web") and result.web else []

    for item in items:
        url = item.url if hasattr(item, "url") else None
        if not url or _should_skip_url(url):
            logger.debug("Skipping URL: %s", url)
            continue

        jobs.append({
            "url": url,
            "title": getattr(item, "title", ""),
            "description": getattr(item, "description", ""),
        })

    logger.info("Search returned %d results for: %s", len(jobs), query)
    return jobs


@retry(max_retries=3, base_delay=1.0, max_delay=30.0, exceptions=(Exception,))
def scrape_search_result(url: str) -> str | None:
    """Scrape a single URL found via search to get its markdown content."""
    from urllib.parse import urlparse

    domain = urlparse(url).netloc.lower()

    # Route LinkedIn URLs through the LinkedIn scraper
    if "linkedin.com" in domain:
        try:
            from src.scraper.linkedin import scrape_linkedin_job
            return scrape_linkedin_job(url)
        except Exception as e:
            logger.warning("LinkedIn scrape failed for %s: %s", url, e)
            return None

    app = get_client()
    try:
        doc = app.scrape(
            url=url,
            formats=["markdown"],
            only_main_content=True,
            wait_for=3000,
        )
        return doc.markdown or None
    except Exception as e:
        logger.warning("Could not scrape %s: %s", url, e)
        return None


@retry(max_retries=3, base_delay=1.0, max_delay=30.0, exceptions=(Exception,))
def crawl_career_page(
    url: str, include_paths: list[str] | None = None, limit: int = 20
) -> list[dict]:
    """Crawl a company career page and return job listing URLs with content.

    Returns a list of dicts with 'url' and 'markdown' keys.
    """
    logger.info("Crawling career page: %s (limit=%d)", url, limit)
    app = get_client()

    kwargs = {"limit": limit}
    if include_paths:
        kwargs["include_paths"] = include_paths

    result = app.crawl(url, **kwargs)

    jobs = []
    items = result.data if hasattr(result, "data") else []
    if not items and isinstance(result, list):
        items = result

    for item in items:
        url_val = None
        markdown = None

        if hasattr(item, "metadata"):
            meta = item.metadata
            if hasattr(meta, "source_url"):
                url_val = meta.source_url
            elif hasattr(meta, "url"):
                url_val = meta.url
            elif isinstance(meta, dict):
                url_val = meta.get("sourceURL") or meta.get("url")
            markdown = item.markdown if hasattr(item, "markdown") else ""
        elif isinstance(item, dict):
            url_val = item.get("metadata", {}).get("sourceURL") or item.get("url")
            markdown = item.get("markdown", "")

        if url_val and markdown:
            jobs.append({"url": url_val, "markdown": markdown})

    logger.info("Crawl returned %d pages from %s", len(jobs), url)
    return jobs


def discover_all() -> list[dict]:
    """Run all configured searches and crawls.

    Search results are scraped individually to get markdown content.
    Returns a combined list of discovered job pages with markdown.
    """
    logger.info("Starting full discovery from config")
    config = load_config()
    all_jobs = []
    seen_urls = set()

    # Pre-load existing URLs from DB to avoid re-scraping known jobs
    from src.db.database import job_exists_by_url
    query_template = config.get("query_template", "{query} job posting apply")

    # Search queries
    for query in config.get("search_queries", []):
        enhanced = query_template.format(query=query)
        click.echo(f"  Searching: {enhanced}")
        logger.info("Discovery search query: %s", enhanced)
        results = search_jobs(enhanced, limit=config.get("search_limit", cfg("discovery", "search_limit", 5)))
        for result in results:
            url = result["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Skip if already in database
            if job_exists_by_url(url):
                logger.debug("Already in DB, skipping: %s", url)
                continue

            markdown = scrape_search_result(url)
            if markdown:
                all_jobs.append({"url": url, "markdown": markdown})

    # Career page crawls
    for company in config.get("company_career_pages", []):
        click.echo(f"  Crawling: {company['name']} ({company['url']})")
        logger.info("Discovery crawling: %s (%s)", company['name'], company['url'])
        results = crawl_career_page(
            url=company["url"],
            include_paths=company.get("include_paths"),
            limit=config.get("crawl_limit", cfg("discovery", "crawl_limit", 20)),
        )
        for job in results:
            if job["url"] not in seen_urls:
                seen_urls.add(job["url"])
                if not job_exists_by_url(job["url"]):
                    all_jobs.append(job)
                else:
                    logger.debug("Already in DB, skipping crawled: %s", job["url"])

    logger.info("Discovery complete: %d unique job pages found", len(all_jobs))
    return all_jobs
