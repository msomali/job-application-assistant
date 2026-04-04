"""Google Gemini LLM provider.

Uses the google-genai SDK (NOT the older google-generativeai package).
Provides structured JSON output, Google Search grounding for company
enrichment, and cost-effective extraction/analysis.
"""

from __future__ import annotations

import logging
import os

from src.llm.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


def _get_client():
    """Lazy import and create the Gemini client."""
    try:
        from google import genai
    except ImportError as exc:
        raise ImportError(
            "google-genai package required for Gemini provider. "
            "Install with: pip install google-genai"
        ) from exc

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY not set. Get one at https://aistudio.google.com/apikey"
        )
    return genai.Client(api_key=api_key)


class GeminiProvider(LLMProvider):
    """Google Gemini provider using the google-genai SDK."""

    def __init__(self) -> None:
        self._client = _get_client()

    @property
    def provider_name(self) -> str:
        return "gemini"

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
        """Send a request to Gemini.

        Args:
            model: Gemini model ID (e.g. "gemini-2.0-flash").
            system: System instruction text.
            messages: Provider-neutral messages.
            max_tokens: Maximum output tokens.
            temperature: Sampling temperature.
            cache_system: Ignored for Gemini (caching is implicit).
        """
        from google.genai import types

        # Build user content from messages
        contents = self._to_gemini_contents(messages)

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        )

        response = self._client.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

        usage = self._extract_usage(response)

        return LLMResponse(
            text=response.text or "",
            provider="gemini",
            model=model,
            usage=usage,
        )

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
        """Generate with concatenated content (Gemini caches implicitly).

        Unlike Anthropic's explicit cache_control blocks, Gemini's context
        caching works automatically. We concatenate the cached and variable
        content into a single user message.
        """
        from google.genai import types

        combined = f"{cached_content}\n\n{variable_content}"

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        )

        response = self._client.models.generate_content(
            model=model,
            contents=combined,
            config=config,
        )

        usage = self._extract_usage(response)

        return LLMResponse(
            text=response.text or "",
            provider="gemini",
            model=model,
            usage=usage,
        )

    def generate_with_grounding(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.5,
    ) -> LLMResponse:
        """Generate with Google Search grounding enabled.

        Used for company enrichment and location scoring where fresh
        web data improves accuracy.
        """
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )

        response = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )

        usage = self._extract_usage(response)

        return LLMResponse(
            text=response.text or "",
            provider="gemini",
            model=model,
            usage=usage,
        )

    @staticmethod
    def _to_gemini_contents(messages: list[dict]) -> str | list:
        """Convert provider-neutral messages to Gemini contents.

        For simple single-user messages, returns the text string directly.
        For multi-turn, returns the list of content dicts.
        """
        if len(messages) == 1 and messages[0]["role"] == "user":
            content = messages[0]["content"]
            if isinstance(content, str):
                return content
            # If content is a list of blocks, concatenate text blocks
            if isinstance(content, list):
                parts = [b["text"] for b in content if isinstance(b, dict) and "text" in b]
                return "\n\n".join(parts)
        # Multi-turn: map roles (Gemini uses "user"/"model" not "assistant")
        gemini_messages = []
        for msg in messages:
            role = "model" if msg["role"] == "assistant" else msg["role"]
            content = msg["content"]
            if isinstance(content, list):
                text = "\n\n".join(
                    b["text"] for b in content if isinstance(b, dict) and "text" in b
                )
            else:
                text = str(content)
            gemini_messages.append({"role": role, "parts": [{"text": text}]})
        return gemini_messages

    @staticmethod
    def _extract_usage(response) -> dict[str, int]:
        """Extract token usage from Gemini response."""
        usage: dict[str, int] = {}
        meta = getattr(response, "usage_metadata", None)
        if meta:
            if hasattr(meta, "input_tokens") and meta.input_tokens is not None:
                usage["input_tokens"] = meta.input_tokens
            if hasattr(meta, "output_tokens") and meta.output_tokens is not None:
                usage["output_tokens"] = meta.output_tokens
            if hasattr(meta, "total_tokens") and meta.total_tokens is not None:
                usage["total_tokens"] = meta.total_tokens
        return usage
