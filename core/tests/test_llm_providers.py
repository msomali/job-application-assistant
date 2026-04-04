"""Tests for LLM providers — mock both Anthropic and Gemini SDK calls."""

from unittest.mock import MagicMock, patch

import pytest


class TestAnthropicProvider:
    def test_generate_calls_sdk(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"key": "value"}')]
        mock_response.usage = MagicMock(
            input_tokens=100,
            output_tokens=50,
            cache_creation_input_tokens=10,
            cache_read_input_tokens=20,
        )

        with patch("src.llm.anthropic_provider.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            from src.llm.anthropic_provider import AnthropicProvider

            provider = AnthropicProvider()
            resp = provider.generate(
                model="claude-haiku-4-5-20251001",
                system="Extract data.",
                messages=[{"role": "user", "content": "test markdown"}],
                max_tokens=3000,
                cache_system=True,
            )

            assert resp.text == '{"key": "value"}'
            assert resp.provider == "anthropic"
            assert resp.model == "claude-haiku-4-5-20251001"
            assert resp.usage["input_tokens"] == 100
            assert resp.usage["output_tokens"] == 50
            assert resp.usage["cache_creation_input_tokens"] == 10

            # Verify cache_control was set on system
            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}

    def test_generate_without_cache(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="hello")]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=5)
        # No cache attributes
        del mock_response.usage.cache_creation_input_tokens
        del mock_response.usage.cache_read_input_tokens

        with patch("src.llm.anthropic_provider.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            from src.llm.anthropic_provider import AnthropicProvider

            provider = AnthropicProvider()
            resp = provider.generate(
                model="claude-haiku-4-5-20251001",
                system="System prompt.",
                messages=[{"role": "user", "content": "hello"}],
                cache_system=False,
            )

            call_kwargs = mock_client.messages.create.call_args[1]
            assert "cache_control" not in call_kwargs["system"][0]
            assert resp.usage["input_tokens"] == 10

    def test_generate_with_cache_two_blocks(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"analysis": "done"}')]
        mock_response.usage = MagicMock(input_tokens=200, output_tokens=100)
        mock_response.usage.cache_creation_input_tokens = 0
        mock_response.usage.cache_read_input_tokens = 150

        with patch("src.llm.anthropic_provider.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_response

            from src.llm.anthropic_provider import AnthropicProvider

            provider = AnthropicProvider()
            resp = provider.generate_with_cache(
                model="claude-sonnet-4-20250514",
                system="Analyze.",
                cached_content="resume data here",
                variable_content="job posting here",
            )

            assert resp.text == '{"analysis": "done"}'
            call_kwargs = mock_client.messages.create.call_args[1]

            # Verify system is cached
            assert call_kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}

            # Verify two user content blocks
            user_content = call_kwargs["messages"][0]["content"]
            assert len(user_content) == 2
            assert user_content[0]["cache_control"] == {"type": "ephemeral"}
            assert "cache_control" not in user_content[1]

    def test_provider_name(self):
        with patch("src.llm.anthropic_provider.anthropic"):
            from src.llm.anthropic_provider import AnthropicProvider

            provider = AnthropicProvider()
            assert provider.provider_name == "anthropic"


class TestGeminiProvider:
    def test_missing_api_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises((RuntimeError, ImportError)):
                from src.llm.gemini_provider import GeminiProvider

                GeminiProvider()

    def test_generate_calls_sdk(self):
        mock_response = MagicMock()
        mock_response.text = '{"key": "value"}'
        mock_response.usage_metadata = MagicMock(
            input_tokens=50,
            output_tokens=30,
            total_tokens=80,
        )

        with patch("src.llm.gemini_provider._get_client") as mock_get:
            mock_client = MagicMock()
            mock_get.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            from src.llm.gemini_provider import GeminiProvider

            provider = GeminiProvider()
            resp = provider.generate(
                model="gemini-2.0-flash",
                system="Extract data.",
                messages=[{"role": "user", "content": "test"}],
            )

            assert resp.text == '{"key": "value"}'
            assert resp.provider == "gemini"
            assert resp.usage["input_tokens"] == 50

    def test_generate_with_grounding(self):
        mock_response = MagicMock()
        mock_response.text = '{"company": "Acme"}'
        mock_response.usage_metadata = MagicMock(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
        )

        with patch("src.llm.gemini_provider._get_client") as mock_get:
            mock_client = MagicMock()
            mock_get.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            from src.llm.gemini_provider import GeminiProvider

            provider = GeminiProvider()
            resp = provider.generate_with_grounding(
                model="gemini-2.5-pro",
                system="Enrich company data.",
                prompt="Company: Acme Corp",
            )

            assert resp.text == '{"company": "Acme"}'
            # Verify tools were passed
            call_kwargs = mock_client.models.generate_content.call_args[1]
            assert "config" in call_kwargs

    def test_provider_name(self):
        with patch("src.llm.gemini_provider._get_client"):
            from src.llm.gemini_provider import GeminiProvider

            provider = GeminiProvider()
            assert provider.provider_name == "gemini"

    def test_empty_response_handled(self):
        mock_response = MagicMock()
        mock_response.text = None
        mock_response.usage_metadata = None

        with patch("src.llm.gemini_provider._get_client") as mock_get:
            mock_client = MagicMock()
            mock_get.return_value = mock_client
            mock_client.models.generate_content.return_value = mock_response

            from src.llm.gemini_provider import GeminiProvider

            provider = GeminiProvider()
            resp = provider.generate(
                model="gemini-2.0-flash",
                system="Test.",
                messages=[{"role": "user", "content": "test"}],
            )

            assert resp.text == ""
            assert resp.usage == {}
