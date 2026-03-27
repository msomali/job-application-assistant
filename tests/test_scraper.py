"""Tests for the Firecrawl scraper in src/scraper/firecrawl_client.py."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.models import JobPosting
from src.scraper import firecrawl_client as scraper

# ---------------------------------------------------------------------------
# _extract_with_claude
# ---------------------------------------------------------------------------


class TestExtractWithClaude:
    def _mock_claude_response(self, data_dict):
        """Build a mock anthropic message containing JSON text."""
        block = MagicMock()
        block.text = json.dumps(data_dict)
        message = MagicMock()
        message.content = [block]
        return message

    def test_returns_parsed_dict(self, sample_job_data):
        mock_msg = self._mock_claude_response(sample_job_data)
        with patch("src.scraper.firecrawl_client.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_msg

            result = scraper._extract_with_claude("# Some markdown content")
            assert result["title"] == "Senior Data Engineer"
            assert result["company"] == "Acme Corp"
            mock_client.messages.create.assert_called_once()

    def test_passes_markdown_in_prompt(self, sample_job_data):
        mock_msg = self._mock_claude_response(sample_job_data)
        with patch("src.scraper.firecrawl_client.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_msg

            scraper._extract_with_claude("UNIQUE_MARKDOWN_CONTENT")
            call_args = mock_client.messages.create.call_args
            prompt_content = call_args[1]["messages"][0]["content"]
            assert "UNIQUE_MARKDOWN_CONTENT" in prompt_content

    def test_invalid_json_raises(self):
        block = MagicMock()
        block.text = "not valid json {{"
        message = MagicMock()
        message.content = [block]

        with patch("src.scraper.firecrawl_client.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = message

            with pytest.raises(json.JSONDecodeError):
                scraper._extract_with_claude("some markdown")


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
    def test_successful_scrape(self, sample_job_data):
        # Mock Firecrawl response
        mock_doc = SimpleNamespace(markdown="# Job Posting\nSenior Data Engineer at Acme")

        # Mock Claude extraction
        block = MagicMock()
        block.text = json.dumps(sample_job_data)
        mock_message = MagicMock()
        mock_message.content = [block]

        with (
            patch("src.scraper.firecrawl_client.get_client") as mock_get_client,
            patch("src.scraper.firecrawl_client.anthropic") as mock_anthropic,
        ):
            mock_app = MagicMock()
            mock_app.scrape.return_value = mock_doc
            mock_get_client.return_value = mock_app

            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_message

            job, raw_md = scraper.scrape_job("https://example.com/job")

            assert isinstance(job, JobPosting)
            assert job.title == "Senior Data Engineer"
            assert raw_md == "# Job Posting\nSenior Data Engineer at Acme"
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
        mock_doc = SimpleNamespace(markdown="# Job")
        block = MagicMock()
        block.text = json.dumps(job_data_no_url)
        mock_message = MagicMock()
        mock_message.content = [block]

        with (
            patch("src.scraper.firecrawl_client.get_client") as mock_get_client,
            patch("src.scraper.firecrawl_client.anthropic") as mock_anthropic,
        ):
            mock_app = MagicMock()
            mock_app.scrape.return_value = mock_doc
            mock_get_client.return_value = mock_app

            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_message

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
        mock_doc = SimpleNamespace(markdown="# Scrolled Job Content")
        block = MagicMock()
        block.text = json.dumps(sample_job_data)
        mock_message = MagicMock()
        mock_message.content = [block]

        with (
            patch("src.scraper.firecrawl_client.get_client") as mock_get_client,
            patch("src.scraper.firecrawl_client.anthropic") as mock_anthropic,
        ):
            mock_app = MagicMock()
            mock_app.scrape.return_value = mock_doc
            mock_get_client.return_value = mock_app

            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_message

            job, raw_md = scraper.scrape_job_with_scroll("https://example.com/scroll-job")

            assert isinstance(job, JobPosting)
            call_kwargs = mock_app.scrape.call_args[1]
            assert "actions" in call_kwargs
            action_types = [a["type"] for a in call_kwargs["actions"]]
            assert "scroll" in action_types
