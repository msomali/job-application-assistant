"""Job discovery via Firecrawl search and company career page crawling."""

import json
import logging
import os
from pathlib import Path

import click
from firecrawl import FirecrawlApp

from src.utils import retry

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent.parent / "data" / "search_config.json"

# Job board aggregator URLs we should skip (they list jobs, not individual postings)
SKIP_DOMAINS = {"linkedin.com", "indeed.com", "glassdoor.com", "ziprecruiter.com"}


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
    """Skip aggregator sites that Firecrawl can't scrape."""
    from urllib.parse import urlparse

    domain = urlparse(url).netloc.lower()
    return any(skip in domain for skip in SKIP_DOMAINS)


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

    # Search queries
    for query in config.get("search_queries", []):
        click.echo(f"  Searching: {query}")
        logger.info("Discovery search query: %s", query)
        results = search_jobs(query, limit=config.get("search_limit", 5))
        for result in results:
            url = result["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)

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
            limit=config.get("crawl_limit", 20),
        )
        for job in results:
            if job["url"] not in seen_urls:
                seen_urls.add(job["url"])
                all_jobs.append(job)

    logger.info("Discovery complete: %d unique job pages found", len(all_jobs))
    return all_jobs
