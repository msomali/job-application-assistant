"""Test Celery task definitions."""

from src.workers.celery_app import celery_app


def test_celery_app_configured():
    assert celery_app.main == "jobapp"
    assert celery_app.conf.task_serializer == "json"


def test_task_registered():
    # After importing tasks module, tasks should be discoverable
    from src.workers import tasks  # noqa: F401
    task_names = list(celery_app.tasks.keys())
    assert "scrape_job" in task_names
    assert "analyze_job" in task_names
    assert "generate_docs" in task_names
    assert "run_discovery" in task_names
