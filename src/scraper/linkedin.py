"""LinkedIn job scraping via Playwright with session persistence.

Navigates LinkedIn's job search UI directly using a saved browser session.
Requires prior login via `job login --site linkedin`.
"""

import asyncio
import logging
import re
from urllib.parse import quote_plus, urljoin

from playwright.async_api import Page, async_playwright

from src.scraper.browser_session import has_session, session_path

logger = logging.getLogger(__name__)

# LinkedIn selectors (updated for 2025/2026 DOM structure)
SELECTORS = {
    "job_cards": "li.jobs-search-results__list-item",
    "job_title": "a.job-card-list__title--link",
    "job_company": "span.job-card-container__primary-description",
    "job_location": "li.job-card-container__metadata-item",
    "job_link": "a.job-card-list__title--link",
    # Individual job page
    "detail_title": "h1.t-24",
    "detail_company": "div.job-details-jobs-unified-top-card__company-name a",
    "detail_location": "div.job-details-jobs-unified-top-card__primary-description-container span",
    "detail_description": "div.jobs-description__content",
    "detail_easy_apply": "button.jobs-apply-button",
    # Fallback selectors (LinkedIn changes DOM frequently)
    "fallback_title": "h1",
    "fallback_description": "div#job-details, article, div[class*='description']",
}


async def _create_linkedin_context(playwright):
    """Create a Playwright browser context with LinkedIn session loaded."""
    if not has_session("linkedin"):
        raise RuntimeError(
            "No LinkedIn session found. Run 'job login --site linkedin' first."
        )

    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        storage_state=str(session_path("linkedin")),
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    return browser, context


async def _extract_job_cards(page: Page, limit: int) -> list[dict]:
    """Extract job card data from LinkedIn search results page."""
    jobs = []

    # Wait for job cards to load
    try:
        await page.wait_for_selector(
            SELECTORS["job_cards"], timeout=10000
        )
    except Exception:
        # Try scrolling to trigger lazy load
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)
        try:
            await page.wait_for_selector(SELECTORS["job_cards"], timeout=5000)
        except Exception:
            logger.warning("No job cards found on page")
            return jobs

    cards = await page.query_selector_all(SELECTORS["job_cards"])

    for card in cards[:limit]:
        try:
            title_el = await card.query_selector(SELECTORS["job_title"])
            company_el = await card.query_selector(SELECTORS["job_company"])
            location_el = await card.query_selector(SELECTORS["job_location"])
            link_el = await card.query_selector(SELECTORS["job_link"])

            title = (await title_el.inner_text()).strip() if title_el else ""
            company = (await company_el.inner_text()).strip() if company_el else ""
            location = (await location_el.inner_text()).strip() if location_el else ""
            href = await link_el.get_attribute("href") if link_el else ""

            if href and not href.startswith("http"):
                href = urljoin("https://www.linkedin.com", href)

            # Clean the URL — strip tracking params
            if href:
                href = re.sub(r"\?.*", "", href)

            if title and href:
                jobs.append({
                    "url": href,
                    "title": title,
                    "description": f"{company} — {location}" if company else location,
                    "company": company,
                    "location": location,
                })
        except Exception as e:
            logger.debug("Error extracting job card: %s", e)
            continue

    return jobs


async def _async_search_linkedin(query: str, limit: int = 25) -> list[dict]:
    """Internal async implementation of LinkedIn job search."""
    encoded_query = quote_plus(query)
    search_url = f"https://www.linkedin.com/jobs/search/?keywords={encoded_query}&refresh=true"

    async with async_playwright() as p:
        browser, context = await _create_linkedin_context(p)
        page = await context.new_page()

        try:
            logger.info("Searching LinkedIn: %s", query)
            await page.goto(search_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)  # Let results settle

            # Check if we're redirected to login
            if "/login" in page.url or "/authwall" in page.url:
                raise RuntimeError(
                    "LinkedIn session expired. Run 'job login --site linkedin' to re-authenticate."
                )

            jobs = await _extract_job_cards(page, limit)
            logger.info("Found %d LinkedIn jobs for: %s", len(jobs), query)

            # Scroll for more results if needed
            while len(jobs) < limit:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                new_jobs = await _extract_job_cards(page, limit)
                if len(new_jobs) <= len(jobs):
                    break  # No new results loaded
                jobs = new_jobs

            return jobs[:limit]

        finally:
            await browser.close()


async def _async_scrape_linkedin_job(url: str) -> str:
    """Internal async implementation of single LinkedIn job scraping."""
    async with async_playwright() as p:
        browser, context = await _create_linkedin_context(p)
        page = await context.new_page()

        try:
            logger.info("Scraping LinkedIn job: %s", url)
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Check for auth wall
            if "/login" in page.url or "/authwall" in page.url:
                raise RuntimeError(
                    "LinkedIn session expired. Run 'job login --site linkedin' to re-authenticate."
                )

            # Try to expand "Show more" if present
            try:
                show_more = await page.query_selector("button[aria-label='Show more']")
                if show_more:
                    await show_more.click()
                    await asyncio.sleep(0.5)
            except Exception:
                pass

            # Extract job details
            parts = []

            # Title
            title_el = await page.query_selector(SELECTORS["detail_title"])
            if not title_el:
                title_el = await page.query_selector(SELECTORS["fallback_title"])
            if title_el:
                parts.append(f"# {(await title_el.inner_text()).strip()}")

            # Company
            company_el = await page.query_selector(SELECTORS["detail_company"])
            if company_el:
                parts.append(f"**Company:** {(await company_el.inner_text()).strip()}")

            # Location
            location_el = await page.query_selector(SELECTORS["detail_location"])
            if location_el:
                parts.append(f"**Location:** {(await location_el.inner_text()).strip()}")

            # Description
            desc_el = await page.query_selector(SELECTORS["detail_description"])
            if not desc_el:
                desc_el = await page.query_selector(SELECTORS["fallback_description"])
            if desc_el:
                desc_text = await desc_el.inner_text()
                parts.append(f"\n## Description\n\n{desc_text.strip()}")

            # Check for Easy Apply
            easy_apply = await page.query_selector(SELECTORS["detail_easy_apply"])
            if easy_apply:
                btn_text = (await easy_apply.inner_text()).strip()
                if "easy apply" in btn_text.lower():
                    parts.append("\n**Application Type:** LinkedIn Easy Apply")

            markdown = "\n\n".join(parts)

            if not markdown.strip():
                # Fallback: get all visible text
                markdown = await page.inner_text("body")
                logger.warning("Used body text fallback for %s", url)

            logger.info("Scraped LinkedIn job: %d chars", len(markdown))
            return markdown

        finally:
            await browser.close()


def search_linkedin(query: str, limit: int = 25) -> list[dict]:
    """Search LinkedIn jobs via Playwright.

    Returns list[dict] with keys: url, title, description
    (Same format as job_discovery.search_jobs)

    Requires saved LinkedIn session via `job login --site linkedin`.
    """
    return asyncio.run(_async_search_linkedin(query, limit))


def scrape_linkedin_job(url: str) -> str:
    """Scrape a single LinkedIn job posting.

    Returns markdown string of job content.
    (Same format as job_discovery.scrape_search_result)
    """
    return asyncio.run(_async_scrape_linkedin_job(url))
