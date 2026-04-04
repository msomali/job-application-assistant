"""Anthropic (Claude) LLM provider.

Wraps the Anthropic SDK, preserving all existing optimizations:
- cache_control on system prompts (90% discount on cached tokens)
- Two-block user messages for analysis/generation (cached resume + variable job)
- Model tiering (Haiku for extraction, Sonnet for analysis/generation)
"""

from __future__ import annotations

import logging

import anthropic

from src.llm.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Claude provider using the Anthropic SDK."""

    def __init__(self) -> None:
        self._client = anthropic.Anthropic()

    @property
    def provider_name(self) -> str:
        return "anthropic"

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
        """Send a request to Claude.

        Messages use the provider-neutral format::

            [{"role": "user", "content": "plain text"}]

        The provider converts them to the Anthropic SDK format.
        """
        # Build system block — with or without caching
        system_blocks = [{"type": "text", "text": system}]
        if cache_system:
            system_blocks[0]["cache_control"] = {"type": "ephemeral"}

        # Convert messages to Anthropic format
        api_messages = self._to_anthropic_messages(messages)

        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_blocks,
            messages=api_messages,
        )

        usage = {}
        if response.usage:
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
            if hasattr(response.usage, "cache_creation_input_tokens"):
                usage["cache_creation_input_tokens"] = (
                    response.usage.cache_creation_input_tokens or 0
                )
            if hasattr(response.usage, "cache_read_input_tokens"):
                usage["cache_read_input_tokens"] = (
                    response.usage.cache_read_input_tokens or 0
                )

        return LLMResponse(
            text=response.content[0].text,
            provider="anthropic",
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
        """Generate with cached system prompt + two-part user message.

        This preserves the existing caching pattern used by analyze_job,
        generate_resume_content, and generate_cover_letter_content:

        - System prompt: cached (``cache_control: ephemeral``)
        - User block 1 (resume/profile): cached
        - User block 2 (job posting): variable per request
        """
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": cached_content,
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": variable_content,
                        },
                    ],
                }
            ],
        )

        usage = {}
        if response.usage:
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
            if hasattr(response.usage, "cache_creation_input_tokens"):
                usage["cache_creation_input_tokens"] = (
                    response.usage.cache_creation_input_tokens or 0
                )
            if hasattr(response.usage, "cache_read_input_tokens"):
                usage["cache_read_input_tokens"] = (
                    response.usage.cache_read_input_tokens or 0
                )

        return LLMResponse(
            text=response.content[0].text,
            provider="anthropic",
            model=model,
            usage=usage,
        )

    @staticmethod
    def _to_anthropic_messages(messages: list[dict]) -> list[dict]:
        """Convert provider-neutral messages to Anthropic SDK format.

        Neutral format: ``[{"role": "user", "content": "text"}]``
        Anthropic format: same for simple strings, passed through for complex content.
        """
        api_messages = []
        for msg in messages:
            content = msg["content"]
            # If content is already a list of blocks, pass through
            # (allows callers to use Anthropic-native block format when needed)
            if isinstance(content, list):
                api_messages.append({"role": msg["role"], "content": content})
            else:
                api_messages.append({"role": msg["role"], "content": str(content)})
        return api_messages
