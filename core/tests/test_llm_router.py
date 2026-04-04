"""Tests for src/llm/router.py — LLM routing and fallback logic."""

from unittest.mock import MagicMock, patch

import pytest

from src.llm.base import LLMResponse
from src.llm.router import LLMRouter, _get_model_for_task, _get_routing, reset_router


@pytest.fixture(autouse=True)
def _clean_router():
    """Reset the singleton router before each test."""
    reset_router()
    yield
    reset_router()


class TestRouting:
    def test_default_routing_is_anthropic(self):
        """All tasks default to Anthropic when no config override."""
        with patch("src.llm.router.cfg", return_value=None):
            assert _get_routing("extraction") == "anthropic"
            assert _get_routing("analysis") == "anthropic"

    def test_config_routing_override(self):
        """Config can route tasks to different providers."""
        routing = {"extraction": "gemini", "analysis": "anthropic"}
        with patch("src.llm.router.cfg", side_effect=lambda s, k: routing if k == "routing" else None):
            assert _get_routing("extraction") == "gemini"
            assert _get_routing("analysis") == "anthropic"


class TestModelForTask:
    def test_default_anthropic_models(self):
        """Returns correct default models when config has no overrides."""
        with patch("src.llm.router.cfg", return_value=None):
            assert _get_model_for_task("anthropic", "extraction") == "claude-haiku-4-5-20251001"
            assert _get_model_for_task("anthropic", "analysis") == "claude-sonnet-4-20250514"
            assert _get_model_for_task("anthropic", "resume_generation") == "claude-sonnet-4-20250514"

    def test_default_gemini_models(self):
        with patch("src.llm.router.cfg", return_value=None):
            assert _get_model_for_task("gemini", "extraction") == "gemini-2.0-flash"
            assert _get_model_for_task("gemini", "analysis") == "gemini-2.5-pro"


class TestLLMRouterGenerate:
    def _mock_provider(self, name="anthropic"):
        provider = MagicMock()
        provider.provider_name = name
        provider.generate.return_value = LLMResponse(
            text='{"result": "ok"}', provider=name, model="test-model",
        )
        provider.generate_with_cache.return_value = LLMResponse(
            text='{"result": "cached"}', provider=name, model="test-model",
        )
        return provider

    def test_generate_routes_to_anthropic(self):
        router = LLMRouter()
        mock_provider = self._mock_provider()
        router._providers["anthropic"] = mock_provider

        with patch("src.llm.router._get_routing", return_value="anthropic"), \
             patch("src.llm.router._get_model_for_task", return_value="test-model"):
            resp = router.generate(
                task="extraction",
                system="Extract data.",
                messages=[{"role": "user", "content": "test"}],
            )

        assert resp.provider == "anthropic"
        mock_provider.generate.assert_called_once()

    def test_generate_with_cache_routes_correctly(self):
        router = LLMRouter()
        mock_provider = self._mock_provider()
        router._providers["anthropic"] = mock_provider

        with patch("src.llm.router._get_routing", return_value="anthropic"), \
             patch("src.llm.router._get_model_for_task", return_value="test-model"):
            resp = router.generate_with_cache(
                task="analysis",
                system="Analyze.",
                cached_content="resume data",
                variable_content="job data",
            )

        assert resp.text == '{"result": "cached"}'
        mock_provider.generate_with_cache.assert_called_once()

    def test_fallback_to_anthropic_on_gemini_failure(self):
        router = LLMRouter()

        gemini_provider = MagicMock()
        gemini_provider.provider_name = "gemini"
        gemini_provider.generate.side_effect = RuntimeError("GOOGLE_API_KEY not set")

        anthropic_provider = self._mock_provider("anthropic")

        router._providers["gemini"] = gemini_provider
        router._providers["anthropic"] = anthropic_provider

        with patch("src.llm.router._get_routing", return_value="gemini"), \
             patch("src.llm.router._get_model_for_task", return_value="test-model"):
            resp = router.generate(
                task="extraction",
                system="Extract.",
                messages=[{"role": "user", "content": "test"}],
            )

        assert resp.provider == "anthropic"
        gemini_provider.generate.assert_called_once()
        anthropic_provider.generate.assert_called_once()

    def test_anthropic_failure_raises_no_fallback(self):
        router = LLMRouter()

        anthropic_provider = MagicMock()
        anthropic_provider.generate.side_effect = RuntimeError("API error")
        router._providers["anthropic"] = anthropic_provider

        with patch("src.llm.router._get_routing", return_value="anthropic"), \
             patch("src.llm.router._get_model_for_task", return_value="test-model"):
            with pytest.raises(RuntimeError, match="API error"):
                router.generate(
                    task="extraction",
                    system="Extract.",
                    messages=[{"role": "user", "content": "test"}],
                )


class TestLLMRouterGrounding:
    def test_grounding_falls_back_on_failure(self):
        router = LLMRouter()

        anthropic_provider = MagicMock()
        anthropic_provider.generate.return_value = LLMResponse(
            text='{"result": "fallback"}', provider="anthropic", model="test",
        )
        router._providers["anthropic"] = anthropic_provider

        # No gemini provider registered — should fall back
        with patch("src.llm.router._get_routing", return_value="gemini"), \
             patch("src.llm.router._get_model_for_task", return_value="test-model"):
            resp = router.generate_with_grounding(
                task="company_enrichment",
                system="Enrich.",
                prompt="Company: Acme",
            )

        assert resp.provider == "anthropic"
