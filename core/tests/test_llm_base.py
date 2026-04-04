"""Tests for src/llm/base.py — LLMResponse and parse_json_response."""

import pytest

from src.llm.base import LLMResponse, parse_json_response


class TestLLMResponse:
    def test_creation(self):
        resp = LLMResponse(text="hello", provider="anthropic", model="claude-haiku-4-5-20251001")
        assert resp.text == "hello"
        assert resp.provider == "anthropic"
        assert resp.model == "claude-haiku-4-5-20251001"
        assert resp.usage == {}

    def test_with_usage(self):
        resp = LLMResponse(
            text="hi",
            provider="gemini",
            model="gemini-2.0-flash",
            usage={"input_tokens": 10, "output_tokens": 20},
        )
        assert resp.usage["input_tokens"] == 10
        assert resp.usage["output_tokens"] == 20

    def test_frozen(self):
        resp = LLMResponse(text="hi", provider="anthropic", model="test")
        with pytest.raises(AttributeError):
            resp.text = "changed"


class TestParseJsonResponse:
    def test_plain_json(self):
        data = parse_json_response('{"title": "Engineer", "company": "Acme"}')
        assert data["title"] == "Engineer"
        assert data["company"] == "Acme"

    def test_with_json_fence(self):
        text = '```json\n{"title": "Engineer"}\n```'
        data = parse_json_response(text)
        assert data["title"] == "Engineer"

    def test_with_plain_fence(self):
        text = '```\n{"title": "Engineer"}\n```'
        data = parse_json_response(text)
        assert data["title"] == "Engineer"

    def test_with_leading_whitespace(self):
        text = '  \n  {"title": "Engineer"}  \n  '
        data = parse_json_response(text)
        assert data["title"] == "Engineer"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            parse_json_response("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="empty"):
            parse_json_response("   \n  ")

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="not valid JSON"):
            parse_json_response("not json at all")

    def test_non_object_raises(self):
        with pytest.raises(ValueError, match="Expected JSON object"):
            parse_json_response("[1, 2, 3]")

    def test_nested_object(self):
        text = '{"outer": {"inner": "value"}, "list": [1, 2]}'
        data = parse_json_response(text)
        assert data["outer"]["inner"] == "value"
        assert data["list"] == [1, 2]

    def test_fence_with_extra_whitespace(self):
        text = '  ```json  \n  {"key": "val"}  \n  ```  '
        data = parse_json_response(text)
        assert data["key"] == "val"
