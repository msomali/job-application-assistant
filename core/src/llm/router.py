"""Config-driven LLM routing with automatic fallback.

Routes each task type (extraction, analysis, generation, etc.) to the
configured provider. Falls back to Anthropic if the preferred provider
fails or isn't available.

Usage::

    from src.llm import get_router
    router = get_router()
    response = router.generate(task="extraction", system="...", messages=[...])
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.config import get as cfg
from src.llm.base import LLMProvider, LLMResponse

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Task types → config keys
TASK_TYPES = {
    "extraction",
    "analysis",
    "resume_generation",
    "cover_letter",
    "computer_use",
    "company_enrichment",
    "location_scoring",
}


def _get_provider_config(provider: str, key: str) -> str | None:
    """Get a model config for a specific provider."""
    providers = cfg("llm", "providers") or {}
    return (providers.get(provider) or {}).get(key)


def _get_routing(task: str) -> str:
    """Get the configured provider for a task type."""
    routing = cfg("llm", "routing") or {}
    return routing.get(task, cfg("llm", "default_provider") or "anthropic")


def _get_model_for_task(provider_name: str, task: str) -> str:
    """Get the model ID for a given provider and task."""
    # Map task types to model config keys
    model_key_map = {
        "extraction": "extraction_model",
        "analysis": "analysis_model",
        "resume_generation": "generation_model",
        "cover_letter": "generation_model",
        "computer_use": "generation_model",
        "company_enrichment": "extraction_model",
        "location_scoring": "extraction_model",
    }
    key = model_key_map.get(task, "extraction_model")
    model = _get_provider_config(provider_name, key)

    # Hardcoded defaults if config is missing
    defaults = {
        "anthropic": {
            "extraction_model": "claude-haiku-4-5-20251001",
            "analysis_model": "claude-sonnet-4-20250514",
            "generation_model": "claude-sonnet-4-20250514",
        },
        "gemini": {
            "extraction_model": "gemini-2.0-flash",
            "analysis_model": "gemini-2.5-pro",
            "generation_model": "gemini-2.5-pro",
        },
    }
    if not model:
        model = defaults.get(provider_name, {}).get(key, "claude-haiku-4-5-20251001")

    return model


class LLMRouter:
    """Config-driven LLM router with fallback.

    Lazily initializes providers — GeminiProvider is only created if
    GOOGLE_API_KEY is set and a task is routed to Gemini.
    """

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def _get_provider(self, name: str) -> LLMProvider:
        """Get or lazily create a provider by name."""
        if name not in self._providers:
            if name == "anthropic":
                from src.llm.anthropic_provider import AnthropicProvider

                self._providers[name] = AnthropicProvider()
            elif name == "gemini":
                from src.llm.gemini_provider import GeminiProvider

                self._providers[name] = GeminiProvider()
            else:
                raise ValueError(f"Unknown LLM provider: {name}")
            logger.info("Initialized %s provider", name)

        return self._providers[name]

    def _with_fallback(
        self,
        task: str,
        call: str,
        **kwargs,
    ) -> LLMResponse:
        """Execute a provider call with fallback to Anthropic.

        Args:
            task: Task type for routing.
            call: Method name to call on the provider ("generate" or "generate_with_cache").
            **kwargs: Arguments passed to the provider method (excluding model).
        """
        provider_name = _get_routing(task)
        model = _get_model_for_task(provider_name, task)

        # Try primary provider
        try:
            provider = self._get_provider(provider_name)
            method = getattr(provider, call)
            response = method(model=model, **kwargs)
            logger.debug(
                "Task '%s' completed by %s/%s (tokens: %s)",
                task, provider_name, model, response.usage,
            )
            return response
        except Exception as exc:
            if provider_name == "anthropic":
                raise  # No fallback if Anthropic itself fails

            logger.warning(
                "Task '%s' failed on %s (%s), falling back to anthropic",
                task, provider_name, exc,
            )

            # Fallback to Anthropic
            fallback_model = _get_model_for_task("anthropic", task)
            fallback = self._get_provider("anthropic")
            method = getattr(fallback, call)
            response = method(model=fallback_model, **kwargs)
            logger.info(
                "Task '%s' completed by anthropic/%s (fallback)", task, fallback_model,
            )
            return response

    def generate(
        self,
        *,
        task: str,
        system: str,
        messages: list[dict],
        max_tokens: int = 2000,
        temperature: float = 0.0,
        cache_system: bool = False,
    ) -> LLMResponse:
        """Route a generation request to the configured provider.

        Args:
            task: Task type for routing (e.g. "extraction", "analysis").
            system: System prompt.
            messages: Provider-neutral messages.
            max_tokens: Max output tokens.
            temperature: Sampling temperature.
            cache_system: Enable system prompt caching.
        """
        return self._with_fallback(
            task=task,
            call="generate",
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            cache_system=cache_system,
        )

    def generate_with_cache(
        self,
        *,
        task: str,
        system: str,
        cached_content: str,
        variable_content: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Route a cached generation request.

        Args:
            task: Task type for routing.
            system: System prompt (always cached on Anthropic).
            cached_content: Static content (e.g. resume).
            variable_content: Per-request content (e.g. job posting).
            max_tokens: Max output tokens.
            temperature: Sampling temperature.
        """
        return self._with_fallback(
            task=task,
            call="generate_with_cache",
            system=system,
            cached_content=cached_content,
            variable_content=variable_content,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def generate_with_grounding(
        self,
        *,
        task: str,
        system: str,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.5,
    ) -> LLMResponse:
        """Route a grounded generation request (Gemini-only feature).

        Falls back to regular generation on Anthropic if Gemini is unavailable.

        Args:
            task: Task type for routing.
            system: System instruction.
            prompt: User prompt.
            max_tokens: Max output tokens.
            temperature: Sampling temperature.
        """
        provider_name = _get_routing(task)
        model = _get_model_for_task(provider_name, task)

        # Try Gemini with grounding first
        if provider_name == "gemini":
            try:
                from src.llm.gemini_provider import GeminiProvider

                provider = self._get_provider("gemini")
                if isinstance(provider, GeminiProvider):
                    return provider.generate_with_grounding(
                        model=model,
                        system=system,
                        prompt=prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
            except Exception as exc:
                logger.warning(
                    "Grounded generation failed on gemini (%s), falling back", exc,
                )

        # Fallback: regular generation on Anthropic
        fallback_model = _get_model_for_task("anthropic", task)
        fallback = self._get_provider("anthropic")
        return fallback.generate(
            model=fallback_model,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            cache_system=True,
        )


# Singleton instance
_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    """Get or create the singleton LLMRouter."""
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router


def reset_router() -> None:
    """Reset the singleton (for testing)."""
    global _router
    _router = None
