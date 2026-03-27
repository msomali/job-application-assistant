"""Centralized logging configuration for the Job Application Assistant."""

import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_FILE = LOG_DIR / "app.log"


def setup_logging() -> None:
    """Set up structured logging with console (INFO) and rotating file (DEBUG) handlers."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()

    # Avoid adding duplicate handlers if called multiple times
    if root_logger.handlers:
        return

    root_logger.setLevel(logging.DEBUG)

    # JSON-like structured format
    fmt = (
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
        '"module": "%(name)s", "message": "%(message)s"}'
    )
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S%z")

    # Console handler — INFO level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Rotating file handler — DEBUG level, 5 MB per file, keep 5 backups
    file_handler = logging.handlers.RotatingFileHandler(
        str(LOG_FILE),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Quiet noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
