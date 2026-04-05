"""Format task events into human-readable Telegram messages."""


def _md_escape(text) -> str:
    if text is None:
        return "N/A"
    text = str(text)
    for ch in "_*`[":
        text = text.replace(ch, f"\\{ch}")
    return text


def format_task_event(event_type: str, data: dict) -> tuple[str, list[list[tuple[str, str]]]]:
    """Format a task event into (message, inline_buttons).

    Returns:
        (text, buttons) where buttons is a list of rows,
        each row a list of (label, callback_data) tuples.
    """
    task_type = data.get("type", "unknown")
    result = data.get("result", {})
    error = data.get("error", "")

    if event_type == "task:failed":
        return f"Task failed: {error}", []

    if event_type != "task:completed":
        return "", []

    if task_type == "scrape":
        title = _md_escape(result.get("title", "Unknown"))
        company = _md_escape(result.get("company", "Unknown"))
        location = result.get("location", "")
        job_id = result.get("job_id", "")
        text = f"Job scraped: *{title} @ {company}*"
        if location:
            text += f" — {_md_escape(location)}"
        buttons = [[("View Job", f"detail:{job_id}")]] if job_id else []
        return text, buttons

    if task_type == "analyze":
        job_id = result.get("job_id", "")
        score = result.get("fit_score", "?")
        gap_count = result.get("gap_count", 0)
        title = _md_escape(result.get("title", "Job"))
        company = _md_escape(result.get("company", ""))
        text = f"Analysis done: *{title} @ {company}* — Fit: *{score}%* ({gap_count} gaps)"
        buttons = []
        if job_id:
            buttons = [[("View", f"detail:{job_id}"), ("Generate", f"generate:{job_id}")]]
        return text, buttons

    if task_type == "generate":
        job_id = result.get("job_id", "")
        title = _md_escape(result.get("title", "Job"))
        company = _md_escape(result.get("company", ""))
        text = f"Docs ready: *{title} @ {company}*"
        return text, []

    if task_type == "discover":
        count = result.get("count", 0)
        top = result.get("top_match", {})
        text = f"Discovery found *{count} new jobs*."
        if top:
            text += f"\nTop: {_md_escape(top.get('title', ''))} @ {_md_escape(top.get('company', ''))} ({top.get('score', '?')}%)"
        buttons = [[("View Jobs", "detail:0")]] if count > 0 else []
        return text, buttons

    return f"Task completed: {task_type}", []
