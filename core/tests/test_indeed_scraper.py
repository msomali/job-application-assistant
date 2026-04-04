"""Tests for Indeed scraping in src/scraper/indeed.py."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.scraper.indeed import (
    SELECTORS,
    _async_scrape_indeed_job,
    _async_search_indeed,
    _extract_job_cards,
    scrape_indeed_job,
    search_indeed,
)


@pytest.fixture()
def mock_page():
    """A mock Playwright page with configurable query_selector results."""
    page = AsyncMock()
    page.url = "https://www.indeed.com/jobs?q=data+engineer"
    page.goto = AsyncMock()
    page.evaluate = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[])
    page.query_selector = AsyncMock(return_value=None)
    page.inner_text = AsyncMock(return_value="")
    page.content = AsyncMock(return_value="<html><body>No results</body></html>")
    page.title = AsyncMock(return_value="Indeed Job Search")
    return page


def _make_card(
    title="Senior Data Engineer",
    company="Acme Corp",
    location="San Francisco, CA",
    salary="$150,000 a year",
    href="/viewjob?jk=abc123",
):
    """Create a mock Indeed job card element."""
    card = AsyncMock()

    title_el = AsyncMock()
    title_el.inner_text = AsyncMock(return_value=title)
    company_el = AsyncMock()
    company_el.inner_text = AsyncMock(return_value=company)
    location_el = AsyncMock()
    location_el.inner_text = AsyncMock(return_value=location)
    salary_el = AsyncMock()
    salary_el.inner_text = AsyncMock(return_value=salary)
    link_el = AsyncMock()
    link_el.get_attribute = AsyncMock(return_value=href)

    selector_map = {
        SELECTORS["job_title"]: title_el,
        SELECTORS["fallback_title"]: None,
        "h2 a": None,
        SELECTORS["job_company"]: company_el,
        SELECTORS["fallback_company"]: None,
        SELECTORS["job_location"]: location_el,
        SELECTORS["fallback_location"]: None,
        SELECTORS["job_link"]: link_el,
        "a[data-jk]": None,
        SELECTORS["job_salary"]: salary_el,
    }

    async def query_selector(selector):
        return selector_map.get(selector)

    card.query_selector = AsyncMock(side_effect=query_selector)
    return card


class TestExtractJobCards:
    def test_extracts_cards(self, mock_page):
        cards = [
            _make_card("Data Engineer", "Google", "NYC", "$180k", "/viewjob?jk=111"),
            _make_card("ML Engineer", "Meta", "Remote", "$200k", "/viewjob?jk=222"),
        ]
        mock_page.query_selector_all = AsyncMock(return_value=cards)

        result = asyncio.run(_extract_job_cards(mock_page, limit=10))
        assert len(result) == 2
        assert result[0]["title"] == "Data Engineer"
        assert result[0]["url"] == "https://www.indeed.com/viewjob?jk=111"
        assert result[0]["company"] == "Google"
        assert result[1]["company"] == "Meta"
        assert result[1]["salary"] == "$200k"

    def test_respects_limit(self, mock_page):
        cards = [_make_card(f"Job {i}", "Co", "Loc", "", f"/viewjob?jk={i}") for i in range(10)]
        mock_page.query_selector_all = AsyncMock(return_value=cards)

        result = asyncio.run(_extract_job_cards(mock_page, limit=3))
        assert len(result) == 3

    def test_skips_cards_without_title(self, mock_page):
        card_no_title = AsyncMock()
        card_no_title.query_selector = AsyncMock(return_value=None)

        mock_page.query_selector_all = AsyncMock(return_value=[card_no_title])
        result = asyncio.run(_extract_job_cards(mock_page, limit=10))
        assert len(result) == 0

    def test_handles_wait_timeout(self, mock_page):
        mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))
        mock_page.query_selector_all = AsyncMock(return_value=[])

        result = asyncio.run(_extract_job_cards(mock_page, limit=10))
        assert result == []

    def test_builds_description_from_parts(self, mock_page):
        cards = [_make_card("Dev", "ACME", "Boston", "$100k", "/viewjob?jk=1")]
        mock_page.query_selector_all = AsyncMock(return_value=cards)

        result = asyncio.run(_extract_job_cards(mock_page, limit=10))
        assert "ACME" in result[0]["description"]
        assert "Boston" in result[0]["description"]
        assert "$100k" in result[0]["description"]

    def test_resolves_relative_urls(self, mock_page):
        cards = [_make_card(href="/viewjob?jk=relative")]
        mock_page.query_selector_all = AsyncMock(return_value=cards)

        result = asyncio.run(_extract_job_cards(mock_page, limit=10))
        assert result[0]["url"].startswith("https://www.indeed.com")


class TestSearchIndeed:
    @patch("src.scraper.indeed._async_search_indeed")
    def test_sync_wrapper_calls_async(self, mock_async):
        mock_async.return_value = [
            {"url": "https://indeed.com/viewjob?jk=1", "title": "Job", "description": "Desc"}
        ]
        result = search_indeed("data engineer", limit=5)
        assert len(result) == 1
        mock_async.assert_called_once_with("data engineer", 5)

    @patch("src.scraper.indeed._create_indeed_context")
    def test_search_builds_url_with_filters(self, mock_ctx):
        """Verify search constructs the correct Indeed URL with config filters."""
        page = AsyncMock()
        page.url = "https://www.indeed.com/jobs?q=data+engineer"
        page.goto = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.title = AsyncMock(return_value="Indeed")
        page.query_selector_all = AsyncMock(return_value=[])
        page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))
        page.evaluate = AsyncMock()

        browser = AsyncMock()
        context = AsyncMock()
        context.new_page = AsyncMock(return_value=page)
        mock_ctx.return_value = (browser, context)

        result = asyncio.run(_async_search_indeed("data engineer", limit=5))
        assert result == []
        page.goto.assert_called()
        call_url = page.goto.call_args_list[0][0][0]
        assert "q=data+engineer" in call_url

    @patch("src.scraper.indeed._create_indeed_context")
    @patch("src.scraper.indeed.cfg")
    def test_search_applies_location_filter(self, mock_cfg, mock_ctx):
        """Verify location filter is appended to URL."""

        def cfg_side_effect(section, key, default=""):
            if section == "indeed" and key == "location":
                return "San Francisco, CA"
            return default

        mock_cfg.side_effect = cfg_side_effect

        page = AsyncMock()
        page.url = "https://www.indeed.com/jobs"
        page.goto = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        page.title = AsyncMock(return_value="Indeed")
        page.query_selector_all = AsyncMock(return_value=[])
        page.wait_for_selector = AsyncMock(side_effect=Exception("Timeout"))
        page.evaluate = AsyncMock()

        browser = AsyncMock()
        context = AsyncMock()
        context.new_page = AsyncMock(return_value=page)
        mock_ctx.return_value = (browser, context)

        asyncio.run(_async_search_indeed("data engineer", limit=5))
        call_url = page.goto.call_args_list[0][0][0]
        assert "San+Francisco" in call_url


class TestScrapeIndeedJob:
    @patch("src.scraper.indeed._async_scrape_indeed_job")
    def test_sync_wrapper(self, mock_async):
        mock_async.return_value = "# Senior Data Engineer\n\nGreat job"
        result = scrape_indeed_job("https://indeed.com/viewjob?jk=123")
        assert "Senior Data Engineer" in result

    @patch("src.scraper.indeed._create_indeed_context")
    def test_extracts_job_details(self, mock_ctx):
        page = AsyncMock()
        page.url = "https://www.indeed.com/viewjob?jk=123"
        page.goto = AsyncMock()

        title_el = AsyncMock()
        title_el.inner_text = AsyncMock(return_value="Staff Data Engineer")
        company_el = AsyncMock()
        company_el.inner_text = AsyncMock(return_value="Netflix")
        location_el = AsyncMock()
        location_el.inner_text = AsyncMock(return_value="Los Gatos, CA")
        salary_el = AsyncMock()
        salary_el.inner_text = AsyncMock(return_value="$200,000 - $300,000 a year")
        desc_el = AsyncMock()
        desc_el.inner_text = AsyncMock(return_value="Build amazing data pipelines.")

        async def query_selector(sel):
            if sel == SELECTORS["detail_title"]:
                return title_el
            if sel == SELECTORS["fallback_detail_title"]:
                return None
            if sel == SELECTORS["detail_company"]:
                return company_el
            if sel == SELECTORS["detail_location"]:
                return location_el
            if sel == SELECTORS["detail_salary"]:
                return salary_el
            if sel == SELECTORS["detail_description"]:
                return desc_el
            if sel == SELECTORS["fallback_detail_description"]:
                return None
            return None

        page.query_selector = AsyncMock(side_effect=query_selector)

        browser = AsyncMock()
        context = AsyncMock()
        context.new_page = AsyncMock(return_value=page)
        mock_ctx.return_value = (browser, context)

        result = asyncio.run(_async_scrape_indeed_job("https://indeed.com/viewjob?jk=123"))
        assert "Staff Data Engineer" in result
        assert "Netflix" in result
        assert "Los Gatos, CA" in result
        assert "$200,000" in result
        assert "Build amazing data pipelines" in result

    @patch("src.scraper.indeed._create_indeed_context")
    def test_falls_back_to_body_text(self, mock_ctx):
        """When no selectors match, falls back to page body text."""
        page = AsyncMock()
        page.url = "https://www.indeed.com/viewjob?jk=456"
        page.goto = AsyncMock()
        page.query_selector = AsyncMock(return_value=None)
        page.inner_text = AsyncMock(return_value="Some raw job text from body")

        browser = AsyncMock()
        context = AsyncMock()
        context.new_page = AsyncMock(return_value=page)
        mock_ctx.return_value = (browser, context)

        result = asyncio.run(_async_scrape_indeed_job("https://indeed.com/viewjob?jk=456"))
        assert "Some raw job text from body" in result
