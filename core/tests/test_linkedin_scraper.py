"""Tests for LinkedIn scraping in src/scraper/linkedin.py."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.scraper.linkedin import (
    _async_scrape_linkedin_job,
    _async_search_linkedin,
    _extract_job_cards,
    scrape_linkedin_job,
    search_linkedin,
)


@pytest.fixture()
def mock_page():
    """A mock Playwright page with configurable query_selector results."""
    page = AsyncMock()
    page.url = "https://www.linkedin.com/jobs/search/?keywords=data+engineer"
    page.goto = AsyncMock()
    page.evaluate = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[])
    page.query_selector = AsyncMock(return_value=None)
    page.inner_text = AsyncMock(return_value="")
    return page


def _make_card(title="Senior Data Engineer", company="Acme Corp", location="SF, CA", href="/jobs/view/123"):
    """Create a mock job card element."""
    from src.scraper.linkedin import SELECTORS

    card = AsyncMock()

    title_el = AsyncMock()
    title_el.inner_text = AsyncMock(return_value=title)
    title_el.get_attribute = AsyncMock(return_value=href)
    company_el = AsyncMock()
    company_el.inner_text = AsyncMock(return_value=company)
    location_el = AsyncMock()
    location_el.inner_text = AsyncMock(return_value=location)

    # Map actual selectors used in _extract_job_cards to mock elements
    selector_map = {
        SELECTORS["job_title"]: title_el,
        SELECTORS["job_company"]: company_el,
        SELECTORS["job_location"]: location_el,
        SELECTORS["job_link"]: title_el,  # title and link use same element
    }

    async def query_selector(selector):
        return selector_map.get(selector)

    card.query_selector = AsyncMock(side_effect=query_selector)
    return card


class TestExtractJobCards:
    def test_extracts_cards(self, mock_page):
        cards = [
            _make_card("Data Engineer", "Google", "NYC", "/jobs/view/111"),
            _make_card("ML Engineer", "Meta", "Remote", "/jobs/view/222"),
        ]
        mock_page.query_selector_all = AsyncMock(return_value=cards)

        result = asyncio.run(_extract_job_cards(mock_page, limit=10))
        assert len(result) == 2
        assert result[0]["title"] == "Data Engineer"
        assert result[0]["url"] == "https://www.linkedin.com/jobs/view/111"
        assert result[1]["company"] == "Meta"

    def test_respects_limit(self, mock_page):
        cards = [_make_card(f"Job {i}", "Co", "Loc", f"/jobs/view/{i}") for i in range(10)]
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


class TestSearchLinkedin:
    @patch("src.scraper.linkedin._async_search_linkedin")
    def test_sync_wrapper_calls_async(self, mock_async):
        mock_async.return_value = [{"url": "https://linkedin.com/jobs/view/1", "title": "Job", "description": "Desc"}]
        result = search_linkedin("data engineer", limit=5)
        assert len(result) == 1
        mock_async.assert_called_once_with("data engineer", 5)

    @patch("src.scraper.linkedin.has_session", return_value=False)
    def test_raises_without_session(self, mock_has):
        with pytest.raises(RuntimeError, match="No LinkedIn session"):
            asyncio.run(_async_search_linkedin("data engineer"))

    @patch("src.scraper.linkedin._create_linkedin_context")
    @patch("src.scraper.linkedin.has_session", return_value=True)
    def test_detects_auth_redirect(self, mock_has, mock_ctx):
        page = AsyncMock()
        page.url = "https://www.linkedin.com/login"
        page.goto = AsyncMock()

        browser = AsyncMock()
        context = AsyncMock()
        context.new_page = AsyncMock(return_value=page)
        mock_ctx.return_value = (browser, context)

        with pytest.raises(RuntimeError, match="session expired"):
            asyncio.run(_async_search_linkedin("data engineer"))


class TestScrapeLinkedinJob:
    @patch("src.scraper.linkedin._async_scrape_linkedin_job")
    def test_sync_wrapper(self, mock_async):
        mock_async.return_value = "# Senior Data Engineer\n\nGreat job"
        result = scrape_linkedin_job("https://linkedin.com/jobs/view/123")
        assert "Senior Data Engineer" in result

    @patch("src.scraper.linkedin._create_linkedin_context")
    @patch("src.scraper.linkedin.has_session", return_value=True)
    def test_extracts_job_details(self, mock_has, mock_ctx):
        page = AsyncMock()
        page.url = "https://www.linkedin.com/jobs/view/123"
        page.goto = AsyncMock()

        # Mock title
        title_el = AsyncMock()
        title_el.inner_text = AsyncMock(return_value="Staff Data Engineer")

        # Mock company
        company_el = AsyncMock()
        company_el.inner_text = AsyncMock(return_value="Netflix")

        # Mock location
        location_el = AsyncMock()
        location_el.inner_text = AsyncMock(return_value="Los Gatos, CA")

        # Mock description
        desc_el = AsyncMock()
        desc_el.inner_text = AsyncMock(return_value="Build amazing data pipelines.")

        # Mock Easy Apply button
        easy_apply_btn = AsyncMock()
        easy_apply_btn.inner_text = AsyncMock(return_value="Easy Apply")

        # Mock show more button
        show_more = None

        async def query_selector(sel):
            if "t-24" in sel:
                return title_el
            if "company-name" in sel:
                return company_el
            if "primary-description" in sel:
                return location_el
            if "description" in sel:
                return desc_el
            if "jobs-apply-button" in sel:
                return easy_apply_btn
            if "Show more" in sel:
                return show_more
            if "h1" in sel:
                return title_el
            return None

        page.query_selector = AsyncMock(side_effect=query_selector)

        browser = AsyncMock()
        context = AsyncMock()
        context.new_page = AsyncMock(return_value=page)
        mock_ctx.return_value = (browser, context)

        result = asyncio.run(_async_scrape_linkedin_job("https://linkedin.com/jobs/view/123"))
        assert "Staff Data Engineer" in result
        assert "Netflix" in result
        assert "Build amazing data pipelines" in result
        assert "Easy Apply" in result
