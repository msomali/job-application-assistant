"""Centralized configuration loaded from data/config.yaml with sensible defaults.

Priority: CLI flag (highest) → config.yaml → hardcoded default (lowest).
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent.parent / "data" / "config.yaml"

# Hardcoded defaults — used when config.yaml is missing or incomplete
_DEFAULTS: dict[str, Any] = {
    "scoring": {
        "min_score_rank": 60,
        "min_score_generate": 70,
        "min_score_notify": 70,
    },
    "discovery": {
        "search_limit": 5,
        "crawl_limit": 20,
        "skip_domains": [
            "linkedin.com",
            "indeed.com",
            "glassdoor.com",
            "ziprecruiter.com",
        ],
    },
    "generation": {
        "batch_limit": 5,
        "output_dir": "output/",
    },
    "telegram": {
        "daily_digest_limit": 5,
    },
    "matching": {
        "fuzzy_threshold": 0.75,
    },
    "indeed": {
        "location": "",
        "fromage": "",
        "remote": "",
        "sort": "",
    },
    "llm": {
        "default_provider": "anthropic",
        "providers": {
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
        },
        "routing": {
            "extraction": "anthropic",
            "analysis": "anthropic",
            "resume_generation": "anthropic",
            "cover_letter": "anthropic",
            "computer_use": "anthropic",
            "company_enrichment": "gemini",
            "location_scoring": "gemini",
        },
    },
}

_config: dict[str, Any] | None = None


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base, preserving nested keys not in override."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> dict[str, Any]:
    """Load config from YAML file, falling back to defaults for missing keys."""
    global _config
    if _config is not None:
        return _config

    user_config: dict[str, Any] = {}
    if CONFIG_PATH.exists():
        try:
            import yaml

            raw = CONFIG_PATH.read_text()
            user_config = yaml.safe_load(raw) or {}
            logger.info("Loaded config from %s", CONFIG_PATH)
        except Exception as e:
            logger.warning("Could not parse %s, using defaults: %s", CONFIG_PATH, e)
    else:
        logger.debug("No config.yaml found at %s, using defaults", CONFIG_PATH)

    _config = _deep_merge(_DEFAULTS, user_config)
    return _config


def get(section: str, key: str, default: Any = None) -> Any:
    """Get a config value by section and key.

    Example: config.get("scoring", "min_score_rank") → 60
    """
    cfg = load_config()
    return cfg.get(section, {}).get(key, default)


def reload() -> dict[str, Any]:
    """Force reload config from disk (useful for testing)."""
    global _config
    _config = None
    return load_config()
