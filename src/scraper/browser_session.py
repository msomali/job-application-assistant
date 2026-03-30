"""Playwright browser session persistence.

Saves and restores browser state (cookies, localStorage, sessionStorage)
between runs so users don't need to re-login for sites like LinkedIn.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SESSION_DIR = Path(__file__).parent.parent.parent / "data" / "browser_sessions"


def session_path(name: str = "default") -> Path:
    """Get path for a named session file."""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    return SESSION_DIR / f"{name}.json"


def has_session(name: str = "default") -> bool:
    """Check if a saved session exists."""
    path = session_path(name)
    return path.exists() and path.stat().st_size > 0


def delete_session(name: str = "default") -> bool:
    """Delete a saved session. Returns True if it existed."""
    path = session_path(name)
    if path.exists():
        path.unlink()
        logger.info("Deleted session: %s", name)
        return True
    return False


def list_sessions() -> list[str]:
    """List all saved session names."""
    if not SESSION_DIR.exists():
        return []
    return [p.stem for p in SESSION_DIR.glob("*.json") if p.stat().st_size > 0]
