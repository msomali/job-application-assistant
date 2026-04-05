"""Test notification formatters."""

from src.notifications.formatters import format_task_event


def test_format_scrape_completed():
    text, buttons = format_task_event("task:completed", {
        "type": "scrape",
        "result": {"title": "ML Engineer", "company": "Google", "job_id": 42},
    })
    assert "ML Engineer" in text
    assert "Google" in text
    assert len(buttons) == 1


def test_format_analyze_completed():
    text, buttons = format_task_event("task:completed", {
        "type": "analyze",
        "result": {"fit_score": 87, "job_id": 42, "title": "ML", "company": "G"},
    })
    assert "87%" in text


def test_format_task_failed():
    text, buttons = format_task_event("task:failed", {
        "error": "Connection timeout",
    })
    assert "failed" in text.lower()
    assert "timeout" in text.lower()
    assert buttons == []


def test_format_unknown_returns_generic():
    text, buttons = format_task_event("task:completed", {"type": "unknown_type"})
    assert "completed" in text.lower()
