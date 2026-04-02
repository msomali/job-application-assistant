"""Tests for LinkedIn Easy Apply in src/agent/linkedin_apply.py."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.agent.linkedin_apply import (
    FormField,
    _best_option_match,
    _detect_fields,
    _resolve_from_resume,
    is_easy_apply,
)


@pytest.fixture()
def mock_page():
    page = AsyncMock()
    page.query_selector = AsyncMock(return_value=None)
    page.query_selector_all = AsyncMock(return_value=[])
    return page


@pytest.fixture()
def resume_data():
    return {
        "name": "John Doe",
        "contact": {
            "email": "john@example.com",
            "phone": "+1-555-0123",
            "city": "San Francisco",
            "state": "CA",
            "zip": "94105",
            "linkedin": "https://linkedin.com/in/johndoe",
            "github": "https://github.com/johndoe",
            "website": "https://johndoe.dev",
        },
    }


class TestIsEasyApply:
    def test_detects_easy_apply(self, mock_page):
        btn = AsyncMock()
        btn.inner_text = AsyncMock(return_value="  Easy Apply  ")
        mock_page.query_selector = AsyncMock(return_value=btn)

        assert asyncio.run(is_easy_apply(mock_page)) is True

    def test_no_button(self, mock_page):
        mock_page.query_selector = AsyncMock(return_value=None)
        assert asyncio.run(is_easy_apply(mock_page)) is False

    def test_apply_button_not_easy(self, mock_page):
        btn = AsyncMock()
        btn.inner_text = AsyncMock(return_value="Apply on company site")
        mock_page.query_selector = AsyncMock(return_value=btn)

        assert asyncio.run(is_easy_apply(mock_page)) is False

    def test_handles_exception(self, mock_page):
        mock_page.query_selector = AsyncMock(side_effect=Exception("DOM error"))
        assert asyncio.run(is_easy_apply(mock_page)) is False


class TestResolveFromResume:
    def test_email(self, resume_data):
        assert _resolve_from_resume("Email address", resume_data) == "john@example.com"

    def test_phone(self, resume_data):
        assert _resolve_from_resume("Phone number", resume_data) == "+1-555-0123"

    def test_first_name(self, resume_data):
        assert _resolve_from_resume("First name", resume_data) == "John"

    def test_last_name(self, resume_data):
        assert _resolve_from_resume("Last name", resume_data) == "Doe"

    def test_full_name(self, resume_data):
        assert _resolve_from_resume("Full name", resume_data) == "John Doe"

    def test_city(self, resume_data):
        assert _resolve_from_resume("City", resume_data) == "San Francisco"

    def test_linkedin_url(self, resume_data):
        assert _resolve_from_resume("LinkedIn URL", resume_data) == "https://linkedin.com/in/johndoe"

    def test_github(self, resume_data):
        assert _resolve_from_resume("GitHub profile", resume_data) == "https://github.com/johndoe"

    def test_unrecognized_field(self, resume_data):
        assert _resolve_from_resume("Favorite color", resume_data) is None

    def test_string_contact(self):
        """Handle legacy format where contact is a string."""
        resume = {"name": "Jane Doe", "contact": "jane@test.com"}
        assert _resolve_from_resume("Full name", resume) == "Jane Doe"
        assert _resolve_from_resume("Email", resume) is None  # string contact can't be indexed


class TestBestOptionMatch:
    def test_exact_match(self):
        assert _best_option_match("Yes", ["Yes", "No"]) == "Yes"

    def test_case_insensitive(self):
        assert _best_option_match("yes", ["Yes", "No"]) == "Yes"

    def test_contains_match(self):
        assert _best_option_match("United States", ["United States of America", "Canada"]) == "United States of America"

    def test_fuzzy_match(self):
        result = _best_option_match("San Francisco", ["San Francisco, CA", "New York, NY"])
        assert result == "San Francisco, CA"

    def test_no_match(self):
        assert _best_option_match("xyz", ["Apple", "Banana"]) is None

    def test_empty_options(self):
        assert _best_option_match("test", []) is None

    def test_empty_target(self):
        assert _best_option_match("", ["Yes", "No"]) is None


class TestDetectFields:
    def test_detects_text_inputs(self, mock_page):
        modal = AsyncMock()

        text_el = AsyncMock()
        text_el.evaluate = AsyncMock(return_value=False)  # not hidden
        text_el.get_attribute = AsyncMock(return_value="first-name")

        # Mock label lookup
        label_el = AsyncMock()
        label_el.inner_text = AsyncMock(return_value="First name")

        async def modal_qsa(selector):
            if "input[type='text']" in selector:
                return [text_el]
            return []

        modal.query_selector_all = AsyncMock(side_effect=modal_qsa)

        async def page_qs(selector):
            if "easy-apply-modal" in selector:
                return modal
            if "label[for=" in selector:
                return label_el
            return None

        mock_page.query_selector = AsyncMock(side_effect=page_qs)
        mock_page.query_selector_all = AsyncMock(side_effect=modal_qsa)

        fields = asyncio.run(_detect_fields(mock_page))
        assert len(fields) >= 1
        assert fields[0].type == "text"

    def test_empty_modal(self, mock_page):
        mock_page.query_selector_all = AsyncMock(return_value=[])
        fields = asyncio.run(_detect_fields(mock_page))
        assert fields == []


class TestFormField:
    def test_default_values(self):
        f = FormField(type="text", label="Name", element_selector="input")
        assert f.options == []
        assert f.required is False
        assert f.value is None

    def test_with_options(self):
        f = FormField(
            type="select",
            label="Country",
            element_selector="select",
            options=["US", "CA", "UK"],
            required=True,
        )
        assert len(f.options) == 3
        assert f.required is True
