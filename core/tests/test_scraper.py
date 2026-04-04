"""Tests for the Firecrawl scraper in src/scraper/firecrawl_client.py."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.llm.base import LLMResponse
from src.models import JobPosting
from src.scraper import firecrawl_client as scraper

# Markdown that passes the _looks_like_job_page heuristic
_JOB_MARKDOWN = "# Job Posting\nApply now. Requirements: experience with Python. Responsibilities: build things."

# ---------------------------------------------------------------------------
# _extract_with_claude
# ---------------------------------------------------------------------------


class TestExtractWithClaude:
    def _mock_router(self, data_dict):
        """Build a mock router returning JSON data."""
        mock_r = MagicMock()
        mock_r.generate.return_value = LLMResponse(
            text=json.dumps(data_dict),
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
        )
        return mock_r

    def test_returns_parsed_dict(self, sample_job_data):
        mock_r = self._mock_router(sample_job_data)
        with patch("src.scraper.firecrawl_client.get_router", return_value=mock_r):
            result = scraper._extract_with_claude(_JOB_MARKDOWN)
            assert result["title"] == "Senior Data Engineer"
            assert result["company"] == "Acme Corp"
            mock_r.generate.assert_called_once()

    def test_passes_markdown_in_prompt(self, sample_job_data):
        mock_r = self._mock_router(sample_job_data)
        with patch("src.scraper.firecrawl_client.get_router", return_value=mock_r):
            scraper._extract_with_claude(_JOB_MARKDOWN)
            call_kwargs = mock_r.generate.call_args[1]
            messages = call_kwargs["messages"]
            assert "Apply now" in messages[0]["content"]

    def test_invalid_json_raises(self):
        mock_r = MagicMock()
        mock_r.generate.return_value = LLMResponse(
            text="not valid json {{",
            provider="anthropic",
            model="test",
        )

        with patch("src.scraper.firecrawl_client.get_router", return_value=mock_r):
            with pytest.raises((json.JSONDecodeError, ValueError)):
                scraper._extract_with_claude(_JOB_MARKDOWN)


# ---------------------------------------------------------------------------
# get_client
# ---------------------------------------------------------------------------


class TestGetClient:
    def test_missing_api_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(RuntimeError, match="FIRECRAWL_API_KEY not set"):
                scraper.get_client()

    def test_returns_client_with_key(self):
        with patch.dict("os.environ", {"FIRECRAWL_API_KEY": "test-key"}):
            with patch("src.scraper.firecrawl_client.FirecrawlApp") as MockApp:
                scraper.get_client()
                MockApp.assert_called_once_with(api_key="test-key")


# ---------------------------------------------------------------------------
# scrape_job — end-to-end with mocks
# ---------------------------------------------------------------------------


class TestScrapeJob:
    def _mock_router(self, data_dict):
        mock_r = MagicMock()
        mock_r.generate.return_value = LLMResponse(
            text=json.dumps(data_dict),
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
        )
        return mock_r

    def test_successful_scrape(self, sample_job_data):
        mock_doc = SimpleNamespace(markdown=_JOB_MARKDOWN)
        mock_r = self._mock_router(sample_job_data)

        with (
            patch("src.scraper.firecrawl_client.get_client") as mock_get_client,
            patch("src.scraper.firecrawl_client.get_router", return_value=mock_r),
        ):
            mock_app = MagicMock()
            mock_app.scrape.return_value = mock_doc
            mock_get_client.return_value = mock_app

            job, raw_md = scraper.scrape_job("https://example.com/job")

            assert isinstance(job, JobPosting)
            assert job.title == "Senior Data Engineer"
            assert raw_md == _JOB_MARKDOWN
            mock_app.scrape.assert_called_once()

    def test_empty_content_raises(self):
        mock_doc = SimpleNamespace(markdown="")

        with patch("src.scraper.firecrawl_client.get_client") as mock_get_client:
            mock_app = MagicMock()
            mock_app.scrape.return_value = mock_doc
            mock_get_client.return_value = mock_app

            with pytest.raises(RuntimeError, match="No content scraped"):
                scraper.scrape_job("https://example.com/empty")

    def test_none_content_raises(self):
        mock_doc = SimpleNamespace(markdown=None)

        with patch("src.scraper.firecrawl_client.get_client") as mock_get_client:
            mock_app = MagicMock()
            mock_app.scrape.return_value = mock_doc
            mock_get_client.return_value = mock_app

            with pytest.raises((RuntimeError, AttributeError)):
                scraper.scrape_job("https://example.com/none")

    def test_sets_application_url_if_missing(self):
        job_data_no_url = {
            "title": "Engineer",
            "company": "Co",
            "location": "Remote",
            "description": "Build things.",
            "requirements": [],
            "responsibilities": [],
            "benefits": [],
            "application_url": None,
        }
        mock_doc = SimpleNamespace(markdown=_JOB_MARKDOWN)
        mock_r = self._mock_router(job_data_no_url)

        with (
            patch("src.scraper.firecrawl_client.get_client") as mock_get_client,
            patch("src.scraper.firecrawl_client.get_router", return_value=mock_r),
        ):
            mock_app = MagicMock()
            mock_app.scrape.return_value = mock_doc
            mock_get_client.return_value = mock_app

            job, _ = scraper.scrape_job("https://example.com/apply-here")
            assert job.application_url == "https://example.com/apply-here"

    def test_firecrawl_api_error(self):
        with patch("src.scraper.firecrawl_client.get_client") as mock_get_client:
            mock_app = MagicMock()
            mock_app.scrape.side_effect = Exception("API rate limit exceeded")
            mock_get_client.return_value = mock_app

            with pytest.raises(Exception, match="API rate limit exceeded"):
                scraper.scrape_job("https://example.com/job")


# ---------------------------------------------------------------------------
# scrape_job_with_scroll
# ---------------------------------------------------------------------------


class TestScrapeJobWithScroll:
    def test_uses_scroll_actions(self, sample_job_data):
        mock_doc = SimpleNamespace(markdown=_JOB_MARKDOWN)
        mock_r = MagicMock()
        mock_r.generate.return_value = LLMResponse(
            text=json.dumps(sample_job_data),
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
        )

        with (
            patch("src.scraper.firecrawl_client.get_client") as mock_get_client,
            patch("src.scraper.firecrawl_client.get_router", return_value=mock_r),
        ):
            mock_app = MagicMock()
            mock_app.scrape.return_value = mock_doc
            mock_get_client.return_value = mock_app

            job, raw_md = scraper.scrape_job_with_scroll("https://example.com/scroll-job")

            assert isinstance(job, JobPosting)
            call_kwargs = mock_app.scrape.call_args[1]
            assert "actions" in call_kwargs
            action_types = [a["type"] for a in call_kwargs["actions"]]
            assert "scroll" in action_types
