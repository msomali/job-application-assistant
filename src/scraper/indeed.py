"""Indeed job scraping via Playwright.

Navigates Indeed's job search UI using Playwright. Unlike LinkedIn,
Indeed does NOT require login for search — but a saved session helps
bypass Cloudflare challenges and get more reliable results.

Optional: `job login --site indeed` for session persistence.
"""

import asyncio
import logging
import re
from urllib.parse import quote_plus, urljoin

from playwright.async_api import Page, async_playwright

from src.config import get as cfg
from src.scraper.browser_session import has_session, session_path

logger = logging.getLogger(__name__)

# Indeed selectors (2025/2026 DOM — Indeed A/B tests frequently)
SELECTORS = {
    # Search results page
    "job_cards": "div.job_seen_beacon",
    "job_title": "h2.jobTitle span",
    "job_company": "span[data-testid='company-name']",
    "job_location": "div[data-testid='text-location']",
    "job_salary": "div.salary-snippet-container",
    "job_link": "h2.jobTitle a",
    "job_date": "span.date",
    # Fallback card selectors
    "fallback_cards": "div.resultContent",
    "fallback_title": "h2 a span",
    "fallback_company": "span.companyName",
    "fallback_location": "div.companyLocation",
    # Individual job page
    "detail_title": "h1.jobsearch-JobInfoHeader-title",
    "detail_company": "div[data-company-name] a, div.jobsearch-InlineCompanyRating a",
    "detail_location": "div[data-testid='inlineHeader-companyLocation'], div.jobsearch-InlineCompanyRating + div",
    "detail_description": "div#jobDescriptionText",
    "detail_salary": "div#salaryInfoAndJobType",
    # Fallback detail selectors
    "fallback_detail_title": "h1",
    "fallback_detail_description": "div[class*='jobDescription'], div[class*='description']",
}

BASE_URL = "https://www.indeed.com"


async def _create_indeed_context(playwright):
    """Create a Playwright browser context, optionally with a saved session."""
    use_session = has_session("indeed")

    browser = await playwright.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )

    ctx_kwargs = {
        "viewport": {"width": 1280, "height": 800},
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "extra_http_headers": {
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    if use_session:
        ctx_kwargs["storage_state"] = str(session_path("indeed"))
        logger.debug("Using saved Indeed session")

    context = await browser.new_context(**ctx_kwargs)
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return browser, context


async def _extract_job_cards(page: Page, limit: int) -> list[dict]:
    """Extract job card data from Indeed search results page."""
    jobs = []

    card_selectors = [
        SELECTORS["job_cards"],
        SELECTORS["fallback_cards"],
        "td.resultContent",
        "div.slider_item",
    ]

    cards = []
    for selector in card_selectors:
        try:
            await page.wait_for_selector(selector, timeout=8000)
            cards = await page.query_selector_all(selector)
            if cards:
                logger.debug("Found %d cards with selector: %s", len(cards), selector)
                break
        except Exception:
            continue

    if not cards:
        # Scroll to trigger lazy loading
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
        html = await page.content()
        logger.warning("No Indeed job cards found. Page length: %d, snippet: %s",
                        len(html), html[:500])
        return jobs

    for card in cards[:limit]:
        try:
            # Title
            title_el = (
                await card.query_selector(SELECTORS["job_title"])
                or await card.query_selector(SELECTORS["fallback_title"])
                or await card.query_selector("h2 a")
            )
            # Company
            company_el = (
                await card.query_selector(SELECTORS["job_company"])
                or await card.query_selector(SELECTORS["fallback_company"])
            )
            # Location
            location_el = (
                await card.query_selector(SELECTORS["job_location"])
                or await card.query_selector(SELECTORS["fallback_location"])
            )
            # Link
            link_el = (
                await card.query_selector(SELECTORS["job_link"])
                or await card.query_selector("h2 a")
                or await card.query_selector("a[data-jk]")
            )
            # Salary (optional)
            salary_el = await card.query_selector(SELECTORS["job_salary"])

            title = (await title_el.inner_text()).strip() if title_el else ""
            company = (await company_el.inner_text()).strip() if company_el else ""
            location = (await location_el.inner_text()).strip() if location_el else ""
            salary = (await salary_el.inner_text()).strip() if salary_el else ""
            href = await link_el.get_attribute("href") if link_el else ""

            if href and not href.startswith("http"):
                href = urljoin(BASE_URL, href)

            # Clean tracking params but keep the jk parameter
            if href:
                href = re.sub(r"&(from|vjk|advn|adid|sjdu|tk|xkcb)[^&]*", "", href)

            if title and href:
                desc_parts = [company, location]
                if salary:
                    desc_parts.append(salary)
                jobs.append({
                    "url": href,
                    "title": title,
                    "description": " — ".join(p for p in desc_parts if p),
                    "company": company,
                    "location": location,
                    "salary": salary,
                })
        except Exception as e:
            logger.debug("Error extracting Indeed job card: %s", e)
            continue

    return jobs


async def _async_search_indeed(query: str, limit: int = 25) -> list[dict]:
    """Internal async implementation of Indeed job search."""
    encoded_query = quote_plus(query)
    search_url = f"{BASE_URL}/jobs?q={encoded_query}"

    # Apply config filters
    location = cfg("indeed", "location", "")
    if location:
        search_url += f"&l={quote_plus(location)}"

    fromage = cfg("indeed", "fromage", "")
    if fromage:
        # Map friendly names to Indeed's fromage values (days)
        fromage_map = {
            "24h": "1", "day": "1", "1": "1",
            "3d": "3", "3": "3",
            "week": "7", "7d": "7", "7": "7",
            "14d": "14", "14": "14",
            "month": "30", "30d": "30", "30": "30",
        }
        search_url += f"&fromage={fromage_map.get(str(fromage), str(fromage))}"

    remote = cfg("indeed", "remote", "")
    if remote:
        search_url += "&remotejob=true"

    sort = cfg("indeed", "sort", "")
    if sort:
        search_url += f"&sort={sort}"

    async with async_playwright() as p:
        browser, context = await _create_indeed_context(p)
        page = await context.new_page()

        try:
            logger.info("Searching Indeed: %s", query)
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # Check for Cloudflare or captcha
            page_content = await page.content()
            if "challenge-running" in page_content or "cf-browser-verification" in page_content:
                logger.warning("Indeed Cloudflare challenge detected — waiting for resolution")
                await asyncio.sleep(5)

            current_url = page.url
            page_title = await page.title()
            logger.debug("Indeed page title: %s, URL: %s", page_title, current_url)

            jobs = await _extract_job_cards(page, limit)
            logger.info("Found %d Indeed jobs for: %s", len(jobs), query)

            # Paginate if needed (Indeed uses start=10, start=20, etc.)
            page_num = 1
            while len(jobs) < limit and page_num < 5:  # Max 5 pages
                page_num += 1
                start = (page_num - 1) * 10
                next_url = f"{search_url}&start={start}"
                await page.goto(next_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
                new_cards = await _extract_job_cards(page, limit - len(jobs))
                if not new_cards:
                    break
                jobs.extend(new_cards)

            return jobs[:limit]

        finally:
            await browser.close()


async def _async_scrape_indeed_job(url: str) -> str:
    """Internal async implementation of single Indeed job scraping."""
    async with async_playwright() as p:
        browser, context = await _create_indeed_context(p)
        page = await context.new_page()

        try:
            logger.info("Scraping Indeed job: %s", url)
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            parts = []

            # Title
            title_el = await page.query_selector(SELECTORS["detail_title"])
            if not title_el:
                title_el = await page.query_selector(SELECTORS["fallback_detail_title"])
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

            # Salary
            salary_el = await page.query_selector(SELECTORS["detail_salary"])
            if salary_el:
                parts.append(f"**Salary:** {(await salary_el.inner_text()).strip()}")

            # Description
            desc_el = await page.query_selector(SELECTORS["detail_description"])
            if not desc_el:
                desc_el = await page.query_selector(SELECTORS["fallback_detail_description"])
            if desc_el:
                desc_text = await desc_el.inner_text()
                parts.append(f"\n## Description\n\n{desc_text.strip()}")

            markdown = "\n\n".join(parts)

            if not markdown.strip():
                markdown = await page.inner_text("body")
                logger.warning("Used body text fallback for %s", url)

            logger.info("Scraped Indeed job: %d chars", len(markdown))
            return markdown

        finally:
            await browser.close()


def _run_async(coro):
    """Run a coroutine, handling both sync and async contexts."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return loop.run_in_executor(pool, asyncio.run, coro)


def search_indeed(query: str, limit: int = 25) -> list[dict]:
    """Search Indeed jobs via Playwright.

    Returns list[dict] with keys: url, title, description, company, location, salary
    (Same format as job_discovery.search_jobs plus salary)

    Does NOT require login — but a saved session (job login --site indeed) helps
    bypass Cloudflare challenges.
    """
    result = _run_async(_async_search_indeed(query, limit))
    if asyncio.isfuture(result) or asyncio.iscoroutine(result):
        raise RuntimeError(
            "Cannot call sync search_indeed from async context. "
            "Use await search_indeed_async()."
        )
    return result


async def search_indeed_async(query: str, limit: int = 25) -> list[dict]:
    """Async version of search_indeed for use in event loops."""
    return await asyncio.to_thread(asyncio.run, _async_search_indeed(query, limit))


def scrape_indeed_job(url: str) -> str:
    """Scrape a single Indeed job posting.

    Returns markdown string of job content.
    """
    result = _run_async(_async_scrape_indeed_job(url))
    if asyncio.isfuture(result) or asyncio.iscoroutine(result):
        raise RuntimeError(
            "Cannot call sync scrape_indeed_job from async context. "
            "Use await scrape_indeed_job_async()."
        )
    return result


async def scrape_indeed_job_async(url: str) -> str:
    """Async version of scrape_indeed_job for use in event loops."""
    return await asyncio.to_thread(asyncio.run, _async_scrape_indeed_job(url))
