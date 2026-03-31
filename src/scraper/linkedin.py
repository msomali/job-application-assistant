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

    browser = await playwright.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = await browser.new_context(
        storage_state=str(session_path("linkedin")),
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
    )
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return browser, context


async def _extract_job_cards(page: Page, limit: int) -> list[dict]:
    """Extract job card data from LinkedIn search results page."""
    jobs = []

    # Try multiple selectors — LinkedIn changes DOM frequently
    card_selectors = [
        SELECTORS["job_cards"],  # li.jobs-search-results__list-item
        "div.job-card-container",
        "li[data-occludable-job-id]",
        "ul.jobs-search__results-list > li",
        "div.jobs-search-results-list li",
    ]

    cards = []
    for selector in card_selectors:
        try:
            await page.wait_for_selector(selector, timeout=5000)
            cards = await page.query_selector_all(selector)
            if cards:
                logger.debug("Found %d cards with selector: %s", len(cards), selector)
                break
        except Exception:
            continue

    if not cards:
        # Try scrolling to trigger lazy load
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)
        for selector in card_selectors:
            try:
                cards = await page.query_selector_all(selector)
                if cards:
                    break
            except Exception:
                continue

    if not cards:
        # Last resort: dump page content for debugging
        html = await page.content()
        logger.warning("No job cards found. Page length: %d, snippet: %s", len(html), html[:500])
        return jobs

    for card in cards[:limit]:
        try:
            # Try multiple selectors for each field
            title_el = (
                await card.query_selector(SELECTORS["job_title"])
                or await card.query_selector("a[class*='title']")
                or await card.query_selector("h3 a")
                or await card.query_selector("a[href*='/jobs/view/']")
            )
            company_el = (
                await card.query_selector(SELECTORS["job_company"])
                or await card.query_selector("h4 a")
                or await card.query_selector("span[class*='company']")
            )
            location_el = (
                await card.query_selector(SELECTORS["job_location"])
                or await card.query_selector("span[class*='location']")
                or await card.query_selector("li[class*='metadata']")
            )
            link_el = title_el or await card.query_selector("a[href*='/jobs/view/']")

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
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)  # Let results render

            # Check if we're redirected to login
            current_url = page.url
            if "/login" in current_url or "/authwall" in current_url:
                raise RuntimeError(
                    "LinkedIn session expired. Run 'job login --site linkedin' to re-authenticate."
                )

            # Debug: log page state
            page_title = await page.title()
            logger.debug("LinkedIn page title: %s, URL: %s", page_title, current_url)

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
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
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


def _run_async(coro):
    """Run a coroutine, handling both sync and async contexts."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Already in an event loop (e.g., Telegram bot) — create a task
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return loop.run_in_executor(pool, asyncio.run, coro)


def search_linkedin(query: str, limit: int = 25) -> list[dict]:
    """Search LinkedIn jobs via Playwright.

    Returns list[dict] with keys: url, title, description
    (Same format as job_discovery.search_jobs)

    Requires saved LinkedIn session via `job login --site linkedin`.
    """
    result = _run_async(_async_search_linkedin(query, limit))
    if asyncio.isfuture(result) or asyncio.iscoroutine(result):
        raise RuntimeError("Cannot call sync search_linkedin from async context. Use await search_linkedin_async().")
    return result


async def search_linkedin_async(query: str, limit: int = 25) -> list[dict]:
    """Async version of search_linkedin for use in event loops."""
    return await asyncio.to_thread(asyncio.run, _async_search_linkedin(query, limit))


def scrape_linkedin_job(url: str) -> str:
    """Scrape a single LinkedIn job posting.

    Returns markdown string of job content.
    (Same format as job_discovery.scrape_search_result)
    """
    result = _run_async(_async_scrape_linkedin_job(url))
    if asyncio.isfuture(result) or asyncio.iscoroutine(result):
        raise RuntimeError("Cannot call sync scrape_linkedin_job from async context. Use await scrape_linkedin_job_async().")
    return result


async def scrape_linkedin_job_async(url: str) -> str:
    """Async version of scrape_linkedin_job for use in event loops."""
    return await asyncio.to_thread(asyncio.run, _async_scrape_linkedin_job(url))
