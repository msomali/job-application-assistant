"""Base abstractions for multi-LLM support.

Defines the common response type, shared JSON parsing, and the provider ABC.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Regex to strip markdown code fences from LLM responses
_FENCE_OPEN = re.compile(r"^\s*```(?:json)?\s*", re.MULTILINE)
_FENCE_CLOSE = re.compile(r"\s*```\s*$", re.MULTILINE)


@dataclass(frozen=True)
class LLMResponse:
    """Unified response from any LLM provider.

    Attributes:
        text: Raw text content from the model.
        provider: Provider name (e.g. "anthropic", "gemini").
        model: Model ID that was used.
        usage: Token usage dict — keys vary by provider but always include
               ``input_tokens`` and ``output_tokens`` when available.
    """

    text: str
    provider: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)


def parse_json_response(text: str) -> dict:
    """Parse a JSON response from an LLM, stripping markdown fences.

    This consolidates the 5+ duplicated parsing patterns across the codebase
    into a single reliable function.

    Args:
        text: Raw LLM response text, possibly wrapped in ```json ... ``` fences.

    Returns:
        Parsed dictionary.

    Raises:
        ValueError: If the text is empty or not valid JSON.
    """
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("LLM returned empty response")

    # Strip markdown code fences
    cleaned = _FENCE_OPEN.sub("", cleaned)
    cleaned = _FENCE_CLOSE.sub("", cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}")

    return data


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier (e.g. 'anthropic', 'gemini')."""

    @abstractmethod
    def generate(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        max_tokens: int = 2000,
        temperature: float = 0.0,
        cache_system: bool = False,
    ) -> LLMResponse:
        """Send a request to the LLM and return the response.

        Args:
            model: Model identifier.
            system: System prompt text.
            messages: Conversation messages in provider-neutral format:
                      ``[{"role": "user", "content": "..."}]``
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature.
            cache_system: Whether to enable caching on the system prompt
                          (provider-specific behavior).
        """

    @abstractmethod
    def generate_with_cache(
        self,
        *,
        model: str,
        system: str,
        cached_content: str,
        variable_content: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Generate with a two-part user message: one cached, one variable.

        This pattern is used by analysis and generation calls where the resume
        (static) is cached and the job posting (variable) changes each call.

        Args:
            model: Model identifier.
            system: System prompt text (always cached).
            cached_content: Static content to cache (e.g. resume JSON).
            variable_content: Per-request content (e.g. job description).
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature.
        """
