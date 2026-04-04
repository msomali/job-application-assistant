"""Multi-LLM support with config-driven routing.

Usage::

    from src.llm import get_router, parse_json_response

    router = get_router()
    response = router.generate(task="extraction", system="...", messages=[...])
    data = parse_json_response(response.text)
"""

from src.llm.base import LLMResponse, parse_json_response
from src.llm.router import get_router, reset_router

__all__ = ["LLMResponse", "get_router", "parse_json_response", "reset_router"]
