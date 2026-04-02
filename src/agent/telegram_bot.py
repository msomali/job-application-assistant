"""Telegram bot for job application notifications and human-in-the-loop approval."""

import asyncio
import json
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.config import get as cfg
from src.db.database import (
    get_analysis,
    get_analytics,
    get_application,
    get_job,
    get_score_calibration,
    get_skill_gaps,
    get_skill_stats,
    init_db,
    list_jobs,
    save_analysis,
    save_job,
    update_application,
)
from src.utils import async_retry

# Pending approvals: job_id -> asyncio.Event
_pending_approvals: dict[int, asyncio.Event] = {}
_approval_results: dict[int, bool] = {}

# Background tasks: prevent garbage collection and log errors
_background_tasks: set[asyncio.Task] = set()

# Users waiting to paste a job description: user_id -> url (optional)
_paste_waiting: dict[int, str] = {}

# Rate limiting: track last heavy command timestamp per user
_last_heavy_cmd: dict[int, float] = {}
_HEAVY_CMD_COOLDOWN = 30  # seconds between discover/search/apply

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"


def _md_escape(text) -> str:
    """Escape Telegram Markdown V1 special characters in dynamic text."""
    if text is None:
        return "N/A"
    text = str(text)
    for ch in "_*`[":
        text = text.replace(ch, f"\\{ch}")
    return text


def _check_rate_limit(user_id: int) -> str | None:
    """Check if user is rate-limited for heavy commands. Returns error message or None."""
    import time

    now = time.time()
    last = _last_heavy_cmd.get(user_id, 0)
    remaining = _HEAVY_CMD_COOLDOWN - (now - last)
    if remaining > 0:
        return f"Please wait {int(remaining)}s before running another heavy command."
    _last_heavy_cmd[user_id] = now
    return None


def _get_config() -> tuple[str, int]:
    """Get bot token and allowed user ID from environment."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    user_id = os.environ.get("TELEGRAM_USER_ID")
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN not set. Create a bot via @BotFather on Telegram."
        )
    if not user_id:
        raise RuntimeError(
            "TELEGRAM_USER_ID not set. Message @userinfobot on Telegram to get your ID."
        )
    return token, int(user_id)


def _is_authorized(update: Update) -> bool:
    """Only respond to the whitelisted user."""
    _, allowed_id = _get_config()
    return update.effective_user.id == allowed_id


# --- Bot commands ---


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    await update.message.reply_text(
        "*Job Application Assistant*\n\n"
        "*Discovery:*\n"
        "/discover - Run job discovery pipeline + send digest\n"
        "/search <query> - Search for jobs with a query\n"
        "/linkedin <query> - Search LinkedIn directly\n"
        "/scrape <url> - Scrape and analyze a single job URL\n"
        "/paste [url] - Paste a job description (for LinkedIn etc.)\n\n"
        "*Browse:*\n"
        "/jobs - List latest jobs with scores\n"
        "/top - Show top matches (score >= 70)\n"
        "/job <id> - Show job details\n"
        "/status - Application tracking summary\n"
        "/analytics - Conversion rates and stats\n"
        "/calibrate - Score calibration vs outcomes\n\n"
        "*Review:*\n"
        "/collect [min\\_score] - Shortlist top-scored jobs\n"
        "/review - Review collected jobs with details\n"
        "/approve <ids> - Generate docs for approved jobs\n"
        "/reject <ids> - Skip these jobs\n\n"
        "*Actions:*\n"
        "/generate <id> - Generate resume + cover letter\n"
        "/apply <id> - Fill out application form (browser)\n"
        "/send <id> - Send generated docs to this chat\n"
        "/update <id> <status> - Update job status (interview/offer/rejected)\n\n"
        "*Session:*\n"
        "/login - How to save browser login sessions\n\n"
        "*During applications:*\n"
        "Reply `submit` to confirm, `skip` to cancel\n"
        "/pause <id> - Pause a running application\n"
        "/resume <id> - Resume a paused application",
        parse_mode="Markdown",
    )


async def cmd_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    init_db()
    jobs = list_jobs(limit=10)
    if not jobs:
        await update.message.reply_text("No jobs found yet.")
        return

    lines = ["*Latest Jobs:*\n"]
    for j in jobs:
        score = j.get("fit_score") or "-"
        status = _md_escape(j.get("status") or "new")
        title = _md_escape(j["title"][:25])
        company = _md_escape(j["company"][:15])
        lines.append(f"`{j['id']:>3}` | {score:>3} | {status} | {title} @ {company}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    init_db()
    jobs = list_jobs(limit=50)
    notify_score = cfg("scoring", "min_score_notify", 70)
    top = [j for j in jobs if j.get("fit_score") and j["fit_score"] >= notify_score]
    top.sort(key=lambda j: j["fit_score"], reverse=True)

    if not top:
        await update.message.reply_text(f"No jobs with fit score >= {notify_score} found.")
        return

    lines = [f"*Top Matches (score >= {notify_score}):*\n"]
    for j in top[:10]:
        status = _md_escape(j.get("status") or "new")
        title = _md_escape(j["title"][:25])
        company = _md_escape(j["company"][:15])
        lines.append(f"`{j['id']:>3}` | {j['fit_score']:>3} | {status} | {title} @ {company}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    init_db()
    if not context.args:
        await update.message.reply_text("Usage: /job <id>")
        return

    try:
        job_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid job ID.")
        return

    job = get_job(job_id)
    if not job:
        await update.message.reply_text(f"Job {job_id} not found.")
        return

    analysis = get_analysis(job_id)

    text = (
        f"*{_md_escape(job['title'])}*\n"
        f"Company: {_md_escape(job['company'])}\n"
        f"Location: {_md_escape(job.get('location', 'N/A'))}\n"
        f"Type: {_md_escape(job.get('job_type', 'N/A'))}\n"
        f"Salary: {_md_escape(job.get('salary_range', 'N/A'))}\n"
        f"URL: {job.get('url', 'N/A')}\n"
    )

    if analysis:
        matching = _md_escape(", ".join(analysis.get("matching_skills", [])[:5]))
        gaps = _md_escape(", ".join(analysis.get("gaps", [])[:3]))
        strategy = _md_escape((analysis.get("tailoring_strategy") or "N/A")[:200])
        text += (
            f"\n*Fit Score: {analysis['fit_score']}/100*\n"
            f"Matching: {matching}\n"
            f"Gaps: {gaps}\n"
            f"Strategy: {strategy}"
        )

    app_data = get_application(job_id)
    if app_data:
        text += f"\n\nStatus: *{_md_escape(app_data.get('status') or 'unknown')}*"
        if app_data.get("resume_path"):
            text += "\nResume: generated"
        if app_data.get("cover_letter_path"):
            text += "\nCover letter: generated"

    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return
    init_db()
    jobs = list_jobs(limit=100)

    total = len(jobs)
    analyzed = sum(1 for j in jobs if j.get("fit_score"))
    docs_gen = sum(1 for j in jobs if j.get("status") == "docs_generated")
    applied = sum(1 for j in jobs if j.get("status") == "applied")

    text = (
        "*Application Tracker:*\n"
        f"Total jobs discovered: {total}\n"
        f"Analyzed: {analyzed}\n"
        f"Docs generated: {docs_gen}\n"
        f"Applied: {applied}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show application analytics and conversion rates."""
    if not _is_authorized(update):
        return
    init_db()
    stats = get_analytics()
    conv = stats["conversion"]
    avg = stats["avg_scores_by_status"]

    lines = [
        "*Application Analytics:*\n",
        f"Jobs discovered (total): {stats['total_discovered']}",
        f"Jobs discovered (last 7 days): {stats['recent_7d']}",
        f"Analyzed: {stats['analyzed']}",
        "",
        "*Pipeline:*",
        f"Docs generated: {stats['docs_generated']}",
        f"Applied: {stats['applied']}",
        f"Interviews: {stats['interview']}",
        f"Offers: {stats['offer']}",
        f"Rejected: {stats['rejected']}",
        "",
        "*Conversion:*",
        f"Discover > Collected: {conv['discover_to_collected']}",
        f"Collected > Docs: {conv['collected_to_docs']}",
        f"Docs > Applied: {conv['docs_to_applied']}",
        f"Applied > Interview: {conv['applied_to_interview']}",
        f"Interview > Offer: {conv['interview_to_offer']}",
    ]

    if avg:
        lines.append("\n*Avg Fit Score by Status:*")
        for status, score in sorted(avg.items()):
            lines.append(f"  {_md_escape(status)}: {score}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_update_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update a job's application status. Usage: /update <id> <status>"""
    if not _is_authorized(update):
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /update <job\\_id> <status>\n\n"
            "Statuses: `discovered`, `docs_generated`, `applied`, "
            "`interview`, `offer`, `rejected`",
            parse_mode="Markdown",
        )
        return

    try:
        job_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid job ID.")
        return

    status = context.args[1].lower()
    valid = {"discovered", "docs_generated", "applied", "interview", "offer", "rejected", "no_response"}
    if status not in valid:
        await update.message.reply_text(
            f"Invalid status. Use one of: {', '.join(sorted(valid))}"
        )
        return

    init_db()
    job = get_job(job_id)
    if not job:
        await update.message.reply_text(f"Job {job_id} not found.")
        return

    update_application(job_id, status=status)
    await update.message.reply_text(
        f"Job `{job_id}` ({_md_escape(job['title'])}) status updated to *{status}*.",
        parse_mode="Markdown",
    )


# --- Action commands ---


async def cmd_discover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Run the full discovery pipeline and send a digest."""
    if not _is_authorized(update):
        return
    rate_msg = _check_rate_limit(update.effective_user.id)
    if rate_msg:
        await update.message.reply_text(rate_msg)
        return
    init_db()
    await update.message.reply_text("Starting job discovery... this may take a few minutes.")

    try:
        from src.analyzer.job_analyzer import analyze_job
        from src.models import JobPosting
        from src.scraper.firecrawl_client import _extract_with_claude
        from src.scraper.job_discovery import discover_all

        results = discover_all()
        new_jobs = []

        from src.db.database import job_exists_by_url

        for result in results:
            url = result["url"]
            markdown = result.get("markdown", "")
            if not markdown.strip():
                continue

            # Skip already-known jobs (discover_all pre-filters, but double-check)
            if job_exists_by_url(url):
                logger.debug("Already in DB, skipping: %s", url)
                continue

            try:
                extracted = _extract_with_claude(markdown)
                job = JobPosting(**extracted)
            except Exception as e:
                logger.debug("Skipping non-job page %s: %s", url, e)
                continue

            job_id = save_job(job.model_dump(), url, markdown)
            analysis = analyze_job(job)
            save_analysis(job_id, analysis.model_dump())

            new_jobs.append({
                "id": job_id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "fit_score": analysis.fit_score,
            })

        logger.info("Telegram discover found %d new jobs", len(new_jobs))
        if new_jobs:
            top = sorted(new_jobs, key=lambda j: j["fit_score"], reverse=True)[:10]
            lines = [f"*Discovery Complete — {len(new_jobs)} new jobs:*\n"]
            for j in top:
                t = _md_escape(j["title"][:25])
                c = _md_escape(j["company"][:15])
                lines.append(f"`{j['id']:>3}` | {j['fit_score']:>3}% | {t} @ {c}")
            if len(new_jobs) > 10:
                lines.append(f"\n...and {len(new_jobs) - 10} more. Use /jobs to see all.")
            lines.append("\nUse /generate <id> to create docs or /apply <id> to apply.")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        else:
            await update.message.reply_text("No new jobs found.")

    except Exception as e:
        logger.exception("Discovery failed")
        await update.message.reply_text(f"Discovery failed: {e}")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search for jobs with a custom query."""
    if not _is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /search <query>\nExample: /search data engineer remote")
        return
    rate_msg = _check_rate_limit(update.effective_user.id)
    if rate_msg:
        await update.message.reply_text(rate_msg)
        return

    init_db()
    query_str = " ".join(context.args)
    await update.message.reply_text(f"Searching: _{query_str}_...", parse_mode="Markdown")

    try:
        from src.analyzer.job_analyzer import analyze_job
        from src.models import JobPosting
        from src.scraper.firecrawl_client import _extract_with_claude
        from src.scraper.job_discovery import scrape_search_result, search_jobs

        results = search_jobs(query_str, limit=5)
        new_jobs = []

        for result in results:
            url = result["url"]
            markdown = scrape_search_result(url)
            if not markdown:
                continue

            try:
                extracted = _extract_with_claude(markdown)
                job = JobPosting(**extracted)
            except Exception as e:
                logger.debug("Skipping non-job page %s: %s", url, e)
                continue

            job_id = save_job(job.model_dump(), url, markdown)
            analysis = analyze_job(job)
            save_analysis(job_id, analysis.model_dump())

            new_jobs.append({
                "id": job_id,
                "title": job.title,
                "company": job.company,
                "fit_score": analysis.fit_score,
            })

        logger.info("Telegram search found %d jobs for: %s", len(new_jobs), query_str)
        if new_jobs:
            lines = [f"*Search results for \"{query_str}\":*\n"]
            for j in sorted(new_jobs, key=lambda j: j["fit_score"], reverse=True):
                t = _md_escape(j["title"][:25])
                c = _md_escape(j["company"][:15])
                lines.append(f"`{j['id']:>3}` | {j['fit_score']:>3}% | {t} @ {c}")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        else:
            await update.message.reply_text("No jobs found for that query.")

    except Exception as e:
        logger.exception("Search failed for query: %s", query_str)
        await update.message.reply_text(f"Search failed: {e}")


async def cmd_linkedin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search LinkedIn for jobs."""
    if not _is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /linkedin <search query>")
        return
    rate_msg = _check_rate_limit(update.effective_user.id)
    if rate_msg:
        await update.message.reply_text(rate_msg)
        return

    query_str = " ".join(context.args)

    from src.scraper.browser_session import has_session

    if not has_session("linkedin"):
        await update.message.reply_text(
            "No LinkedIn session. Run `job login --site linkedin` on your machine first."
        )
        return

    init_db()
    await update.message.reply_text(f"Searching LinkedIn: {query_str}")

    try:
        from src.analyzer.job_analyzer import analyze_job
        from src.scraper.firecrawl_client import _extract_with_claude
        from src.scraper.linkedin import scrape_linkedin_job_async, search_linkedin_async

        limit = cfg("discovery", "search_limit", 5)
        results = await search_linkedin_async(query_str, limit=limit)
        if not results:
            await update.message.reply_text("No LinkedIn jobs found.")
            return

        lines = [f"*LinkedIn: {len(results)} results*\n"]
        for result in results:
            url = result["url"]
            try:
                markdown = await scrape_linkedin_job_async(url)
                if not markdown:
                    logger.warning("Empty markdown from LinkedIn scrape: %s", url)
                    continue
                try:
                    extracted = _extract_with_claude(markdown)
                except (ValueError, json.JSONDecodeError) as exc:
                    # Claude extraction failed — fall back to card data + scraped markdown
                    logger.warning(
                        "Claude extraction failed for %s (%s), using card data", url, exc
                    )
                    extracted = {
                        "title": result.get("title", "Unknown"),
                        "company": result.get("company", "Unknown"),
                        "location": result.get("location", ""),
                        "description": markdown,
                    }
                from src.models import JobPosting
                job = JobPosting(**extracted)
                job_id = save_job(job.model_dump(), url, markdown)
                analysis = analyze_job(job)
                save_analysis(job_id, analysis.model_dump())
                lines.append(
                    f"`{job_id:>3}` | {analysis.fit_score:>3}% | "
                    f"{_md_escape(job.title[:25])} @ {_md_escape(job.company[:15])}"
                )
            except Exception as e:
                logger.warning("LinkedIn scrape/analysis failed for %s: %s", url, e)
                continue

        if len(lines) > 1:
            lines.append("\nUse /job <id> for details.")
            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        else:
            await update.message.reply_text("Could not parse any LinkedIn results.")

    except Exception as e:
        logger.exception("LinkedIn search failed: %s", query_str)
        await update.message.reply_text(f"LinkedIn search failed: {e}")


async def cmd_scrape(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Scrape and analyze a single job URL."""
    if not _is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /scrape <url>")
        return

    init_db()
    url = context.args[0]
    await update.message.reply_text(f"Scraping: {url}")

    try:
        from src.analyzer.job_analyzer import analyze_job
        from src.scraper.firecrawl_client import scrape_job

        job, raw_markdown = scrape_job(url)
        job_id = save_job(job.model_dump(), url, raw_markdown)
        analysis = analyze_job(job)
        save_analysis(job_id, analysis.model_dump())

        text = (
            f"*{_md_escape(job.title)}* at {_md_escape(job.company)}\n"
            f"Location: {_md_escape(job.location or 'N/A')}\n"
            f"Fit Score: *{analysis.fit_score}/100*\n"
            f"Matching: {_md_escape(', '.join(analysis.matching_skills[:5]))}\n"
            f"Gaps: {_md_escape(', '.join(analysis.gaps[:3]))}\n"
            f"\nJob ID: `{job_id}`\n"
            f"Use /generate {job_id} to create docs."
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    except Exception as e:
        logger.exception("Scrape failed for URL: %s", url)
        await update.message.reply_text(f"Scrape failed: {e}")


async def cmd_paste(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enter paste mode — next message will be treated as a job description."""
    if not _is_authorized(update):
        return

    # Optional URL argument
    url = context.args[0] if context.args else ""
    user_id = update.effective_user.id
    _paste_waiting[user_id] = url

    await update.message.reply_text(
        "Paste the job description below.\n"
        "Copy everything from the job posting (title, company, requirements, etc.) "
        "and send it as one message.\n\n"
        "Send /cancel to exit paste mode.",
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel paste mode."""
    if not _is_authorized(update):
        return
    user_id = update.effective_user.id
    if user_id in _paste_waiting:
        del _paste_waiting[user_id]
        await update.message.reply_text("Paste mode cancelled.")
    else:
        await update.message.reply_text("Nothing to cancel.")


async def _handle_pasted_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Process a pasted job description. Returns True if handled."""
    user_id = update.effective_user.id
    if user_id not in _paste_waiting:
        return False

    url = _paste_waiting.pop(user_id)
    text = update.message.text.strip()

    if len(text) < 50:
        await update.message.reply_text(
            "That looks too short for a job description. Try again or /cancel."
        )
        _paste_waiting[user_id] = url  # Keep in paste mode
        return True

    init_db()
    await update.message.reply_text("Analyzing pasted job description...")

    try:
        from src.analyzer.job_analyzer import analyze_job
        from src.models import JobPosting
        from src.scraper.firecrawl_client import _extract_with_claude

        extracted = _extract_with_claude(text)
        job = JobPosting(**extracted)

        # Use provided URL or generate a placeholder
        if not url:
            url = f"paste://{job.company}-{job.title}".replace(" ", "-").lower()

        job_id = save_job(job.model_dump(), url, text)
        analysis = analyze_job(job)
        save_analysis(job_id, analysis.model_dump())

        reply = (
            f"*{_md_escape(job.title)}* at {_md_escape(job.company)}\n"
            f"Location: {_md_escape(job.location or 'N/A')}\n"
            f"Type: {_md_escape(job.job_type or 'N/A')}\n"
            f"Salary: {_md_escape(job.salary_range or 'N/A')}\n\n"
            f"*Fit Score: {analysis.fit_score}/100*\n"
            f"Matching: {_md_escape(', '.join(analysis.matching_skills[:5]))}\n"
            f"Gaps: {_md_escape(', '.join(analysis.gaps[:3]))}\n"
            f"\nJob ID: `{job_id}`\n"
            f"Use /generate {job_id} to create docs."
        )
        await update.message.reply_text(reply, parse_mode="Markdown")

    except Exception as e:
        logger.exception("Failed to analyze pasted description")
        await update.message.reply_text(f"Failed to analyze: {e}")

    return True


async def cmd_generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate resume + cover letter for a job."""
    if not _is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /generate <job_id> [pages]")
        return

    try:
        job_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid job ID.")
        return

    # Optional pages argument (default 1)
    pages = 1
    if len(context.args) > 1:
        try:
            pages = max(1, min(3, int(context.args[1])))
        except ValueError:
            pass

    init_db()
    job_data = get_job(job_id)
    if not job_data:
        await update.message.reply_text(f"Job {job_id} not found.")
        return

    analysis_data = get_analysis(job_id)
    if not analysis_data:
        await update.message.reply_text(f"No analysis for job {job_id}. Use /scrape first.")
        return

    await update.message.reply_text(
        f"Generating docs for: {job_data['title']} at {job_data['company']}..."
    )

    try:
        from src.analyzer.job_analyzer import load_master_resume
        from src.generator.cover_letter_generator import (
            generate_cover_letter_content,
            render_cover_letter,
        )
        from src.generator.resume_generator import generate_resume_content, render_resume
        from src.models import JobAnalysis, JobPosting

        job = JobPosting(**job_data)
        analysis = JobAnalysis(**analysis_data)
        master_resume = load_master_resume()

        slug = re.sub(r"[^a-z0-9]+", "-", f"{job.company}-{job.title}".lower()).strip("-")[:40]
        date_str = datetime.now(UTC).strftime("%Y%m%d")
        output_dir = OUTPUT_DIR / f"{slug}_{date_str}_{job_id}"

        resume_content = generate_resume_content(job, analysis, master_resume, pages=pages)
        resume_pdf = render_resume(resume_content, master_resume, output_dir, pages=pages)
        update_application(job_id, resume_path=str(resume_pdf))

        cover_letter_content = generate_cover_letter_content(job, analysis, master_resume)
        cover_letter_pdf = render_cover_letter(cover_letter_content, master_resume, output_dir)
        update_application(job_id, cover_letter_path=str(cover_letter_pdf), status="docs_generated")

        # Send the PDFs
        with open(str(resume_pdf), "rb") as f:
            await update.message.reply_document(
                document=f, caption=f"Resume — {job.title} at {job.company}"
            )
        with open(str(cover_letter_pdf), "rb") as f:
            await update.message.reply_document(
                document=f, caption=f"Cover Letter — {job.title} at {job.company}"
            )

        await update.message.reply_text(
            f"Docs generated for job `{job_id}`.\n"
            f"Use /apply {job_id} to fill out the application.",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.exception("Document generation failed for job ID: %d", job_id)
        await update.message.reply_text(f"Generation failed: {e}")


async def cmd_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fill out a job application using browser automation."""
    if not _is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /apply <job_id>")
        return
    rate_msg = _check_rate_limit(update.effective_user.id)
    if rate_msg:
        await update.message.reply_text(rate_msg)
        return

    try:
        job_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid job ID.")
        return

    init_db()
    job_data = get_job(job_id)
    if not job_data:
        await update.message.reply_text(f"Job {job_id} not found.")
        return

    app_data = get_application(job_id)
    if not app_data or not app_data.get("resume_path"):
        await update.message.reply_text(
            f"No documents for job {job_id}. Use /generate {job_id} first."
        )
        return

    application_url = job_data.get("application_url") or job_data.get("url", "")
    if not application_url:
        await update.message.reply_text(f"No application URL for job {job_id}.")
        return

    await update.message.reply_text(
        f"Starting application for: *{_md_escape(job_data['title'])}* at {_md_escape(job_data['company'])}\n"
        f"URL: {application_url}\n\n"
        "Opening browser and filling form...",
        parse_mode="Markdown",
    )

    async def _run_apply():
        """Background task so the bot can still process approval replies."""
        try:
            from src.agent.computer_use import fill_application
            from src.analyzer.job_analyzer import load_master_resume

            master_resume = load_master_resume()

            result = await fill_application(
                application_url=application_url,
                master_resume=master_resume,
                resume_path=app_data["resume_path"],
                cover_letter_path=app_data.get("cover_letter_path", ""),
                job_id=job_id,
                headless=False,
            )

            if result["status"] == "submitted":
                await send_notification(f"Application for job #{job_id} submitted!")
            elif result["status"] == "failed":
                reason = result.get("message", "Unknown error")
                await send_notification(f"Application for job #{job_id} failed: {reason}")
            elif result["status"] == "skipped_by_user":
                await send_notification(f"Application for job #{job_id} was skipped.")
            elif result["status"] == "blocked":
                await send_notification(
                    f"Application got stuck: {result.get('message', 'unknown reason')}"
                )
            else:
                await send_notification(
                    f"Application result: {result['status']} "
                    f"({result.get('steps_taken', 0)} steps)"
                )

        except Exception as e:
            logger.exception("Application failed for job ID: %d", job_id)
            await send_notification(f"Application failed: {e}")

    task = asyncio.create_task(_run_apply(), name=f"apply_job_{job_id}")

    def _task_done(t: asyncio.Task):
        _background_tasks.discard(t)
        if t.cancelled():
            logger.warning("Apply task for job %d was cancelled", job_id)
        elif exc := t.exception():
            logger.exception("Apply task for job %d failed: %s", job_id, exc)

    task.add_done_callback(_task_done)
    _background_tasks.add(task)


async def cmd_collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shortlist top-scored jobs for review."""
    if not _is_authorized(update):
        return
    rate_msg = _check_rate_limit(update.effective_user.id)
    if rate_msg:
        await update.message.reply_text(rate_msg)
        return

    min_score = 60
    if context.args:
        try:
            min_score = int(context.args[0])
        except ValueError:
            pass

    init_db()
    from src.db.database import bulk_collect, get_uncollected_jobs

    uncollected = get_uncollected_jobs(min_score=min_score, limit=20)
    if not uncollected:
        await update.message.reply_text(
            f"No uncollected jobs with score >= {min_score}."
        )
        return

    job_ids = [j["id"] for j in uncollected]
    count = bulk_collect(job_ids)

    lines = [f"*Collected {count} jobs* (score >= {min_score}):\n"]
    for j in uncollected:
        lines.append(
            f"#{j['id']} — {j['fit_score']}pts — {_md_escape(j['title'])} at {_md_escape(j['company'])}"
        )
    lines.append("\nUse /review to see details, /approve <ids> to generate docs.")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Review collected jobs before approving."""
    if not _is_authorized(update):
        return

    init_db()
    from src.db.database import get_collected_jobs

    jobs = get_collected_jobs()
    if not jobs:
        await update.message.reply_text("No collected jobs to review. Use /collect first.")
        return

    for j in jobs:
        skills = ", ".join(j.get("matching_skills", [])[:5])
        gaps = ", ".join(j.get("gaps", [])[:3])
        text = (
            f"*#{j['id']} — {_md_escape(j['title'])}*\n"
            f"Company: {_md_escape(j['company'])} | Location: {_md_escape(j['location'] or 'N/A')}\n"
            f"Score: {j['fit_score']}/100\n"
            f"Skills: {_md_escape(skills)}\n"
        )
        if gaps:
            text += f"Gaps: {_md_escape(gaps)}\n"
        strategy = j.get("tailoring_strategy", "")
        if strategy:
            text += f"Strategy: {_md_escape(strategy[:150])}\n"
        await update.message.reply_text(text, parse_mode="Markdown")

    await update.message.reply_text(
        f"{len(jobs)} jobs in review.\n"
        "/approve 1 2 3 — generate docs\n"
        "/reject 4 5 — skip these jobs"
    )


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve collected jobs and generate docs."""
    if not _is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /approve <job_id> [job_id ...]")
        return
    rate_msg = _check_rate_limit(update.effective_user.id)
    if rate_msg:
        await update.message.reply_text(rate_msg)
        return

    init_db()
    from src.analyzer.job_analyzer import load_master_resume
    from src.generator.cover_letter_generator import (
        generate_cover_letter_content,
        render_cover_letter,
    )
    from src.generator.resume_generator import generate_resume_content, render_resume
    from src.models import JobAnalysis, JobPosting

    master_resume = load_master_resume()
    output_dir = Path(__file__).parent.parent.parent / "output"

    for arg in context.args:
        try:
            job_id = int(arg)
        except ValueError:
            await update.message.reply_text(f"Invalid ID: {arg}")
            continue

        job_data = get_job(job_id)
        if not job_data:
            await update.message.reply_text(f"Job {job_id} not found.")
            continue

        analysis_data = get_analysis(job_id)
        if not analysis_data:
            await update.message.reply_text(f"No analysis for job {job_id}.")
            continue

        await update.message.reply_text(
            f"Generating docs for #{job_id}: {job_data['title']} at {job_data['company']}..."
        )

        try:
            job = JobPosting(**{k: job_data[k] for k in JobPosting.model_fields if k in job_data})
            analysis = JobAnalysis(
                **{k: analysis_data[k] for k in JobAnalysis.model_fields if k in analysis_data}
            )

            import re
            slug = re.sub(r"[^a-z0-9]+", "-", f"{job.company}-{job.title}".lower()).strip("-")[:40]
            date_str = datetime.now(UTC).strftime("%Y%m%d")
            job_output = output_dir / f"{slug}_{date_str}_{job_id}"

            resume_content = generate_resume_content(job, analysis, master_resume)
            resume_pdf = render_resume(resume_content, master_resume, job_output)
            update_application(job_id, resume_path=str(resume_pdf))

            cover_content = generate_cover_letter_content(job, analysis, master_resume)
            cover_pdf = render_cover_letter(cover_content, master_resume, job_output)
            update_application(job_id, cover_letter_path=str(cover_pdf), status="docs_generated")

            await update.message.reply_text(
                f"Docs ready for #{job_id}. Use /send {job_id} or /apply {job_id}."
            )
        except Exception as e:
            logger.exception("Doc generation failed for job %d", job_id)
            await update.message.reply_text(f"Failed for #{job_id}: {e}")


async def cmd_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject collected jobs."""
    if not _is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /reject <job_id> [job_id ...]")
        return

    init_db()
    rejected = []
    for arg in context.args:
        try:
            job_id = int(arg)
            update_application(job_id, status="rejected")
            rejected.append(str(job_id))
        except (ValueError, Exception) as e:
            await update.message.reply_text(f"Error rejecting {arg}: {e}")

    if rejected:
        await update.message.reply_text(f"Rejected jobs: {', '.join(rejected)}")


async def cmd_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send generated docs for a job to the chat."""
    if not _is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /send <job_id>")
        return

    try:
        job_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid job ID.")
        return

    init_db()
    job_data = get_job(job_id)
    if not job_data:
        await update.message.reply_text(f"Job {job_id} not found.")
        return

    app_data = get_application(job_id)
    if not app_data:
        await update.message.reply_text(f"No documents for job {job_id}. Use /generate {job_id} first.")
        return

    sent = False
    if app_data.get("resume_path") and Path(app_data["resume_path"]).exists():
        with open(app_data["resume_path"], "rb") as f:
            await update.message.reply_document(
                document=f, caption=f"Resume — {job_data['title']} at {job_data['company']}"
            )
        sent = True

    if app_data.get("cover_letter_path") and Path(app_data["cover_letter_path"]).exists():
        with open(app_data["cover_letter_path"], "rb") as f:
            await update.message.reply_document(
                document=f, caption=f"Cover Letter — {job_data['title']} at {job_data['company']}"
            )
        sent = True

    if not sent:
        await update.message.reply_text("No document files found. They may have been moved or deleted.")


# --- Approval flow ---


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free-text messages: paste mode or approval flow."""
    if not _is_authorized(update):
        return

    # Check paste mode first
    if await _handle_pasted_description(update, context):
        return

    text = update.message.text.strip().lower()

    if text in ("submit", "yes", "approve", "y"):
        for job_id, event in list(_pending_approvals.items()):
            _approval_results[job_id] = True
            event.set()
            del _pending_approvals[job_id]
            await update.message.reply_text(f"Approved. Submitting application for job #{job_id}.")
            return
        await update.message.reply_text("No pending approvals.")

    elif text in ("skip", "no", "cancel", "n"):
        for job_id, event in list(_pending_approvals.items()):
            _approval_results[job_id] = False
            event.set()
            del _pending_approvals[job_id]
            await update.message.reply_text(f"Skipped application for job #{job_id}.")
            return
        await update.message.reply_text("No pending approvals.")


# --- Functions called by the agent ---


@async_retry(max_retries=3, base_delay=1.0, max_delay=30.0, exceptions=(Exception,))
async def send_notification(message: str) -> None:
    """Send a notification message to the user via Telegram."""
    token, user_id = _get_config()
    bot = Bot(token=token)
    await bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown")


@async_retry(max_retries=3, base_delay=1.0, max_delay=30.0, exceptions=(Exception,))
async def send_photo(photo_path: str, caption: str = "") -> None:
    """Send a screenshot to the user via Telegram."""
    token, user_id = _get_config()
    bot = Bot(token=token)
    with open(photo_path, "rb") as photo:
        await bot.send_photo(chat_id=user_id, photo=photo, caption=caption)


@async_retry(max_retries=3, base_delay=1.0, max_delay=30.0, exceptions=(Exception,))
async def send_document(doc_path: str, caption: str = "") -> None:
    """Send a document (PDF) to the user via Telegram."""
    token, user_id = _get_config()
    bot = Bot(token=token)
    with open(doc_path, "rb") as doc:
        await bot.send_document(chat_id=user_id, document=doc, caption=caption)


async def cmd_calibrate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show score calibration — correlate fit scores with application outcomes."""
    if not _is_authorized(update):
        return
    init_db()

    cal = get_score_calibration()
    if cal["total_with_outcomes"] == 0:
        await update.message.reply_text(
            "No application outcomes yet.\n"
            "Use /update <id> <status> to track results (interview, rejected, offer)."
        )
        return

    lines = ["*Score Calibration Report:*\n"]
    lines.append("*Avg Fit Score by Outcome:*")
    for status, data in cal["avg_by_status"].items():
        lines.append(
            f"  {status}: {data['avg_score']:.0f} avg "
            f"({data['min_score']}-{data['max_score']}, n={data['count']})"
        )

    if cal["recommended_threshold"] is not None:
        lines.append(f"\n*Recommended min score: {cal['recommended_threshold']}*")
    else:
        lines.append("\nNeed both rejected + interview data for threshold.")

    if any(cal["penalty_analysis"].values()):
        lines.append("\n*Penalty Patterns:*")
        for bucket, rules in cal["penalty_analysis"].items():
            if rules:
                lines.append(f"_{bucket.title()}:_")
                for rule, count in sorted(rules.items(), key=lambda x: -x[1]):
                    lines.append(f"  {rule}: {count}x")

    lines.append(f"\nTotal with outcomes: {cal['total_with_outcomes']}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show top in-demand skills and skill gaps."""
    if not _is_authorized(update):
        return
    init_db()

    stats = get_skill_stats(limit=20)
    if not stats:
        await update.message.reply_text("No skill data yet. Run /discover first.")
        return

    lines = ["*Top In-Demand Skills:*\n"]
    for i, s in enumerate(stats, 1):
        lines.append(f"{i}. {s['skill']} ({s['job_count']} jobs)")

    # Add skill gaps
    from src.analyzer.job_analyzer import load_master_resume
    try:
        master_resume = load_master_resume()
        gaps = get_skill_gaps(master_resume.get("skills", []), limit=10)
        if gaps:
            lines.append("\n*Skills You're Missing:*\n")
            for g in gaps:
                lines.append(f"- {g['skill']} ({g['job_count']} jobs)")
    except FileNotFoundError:
        pass

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pause a running application."""
    if not _is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /pause <job_id>")
        return

    try:
        job_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid job ID.")
        return

    from src.agent.computer_use import request_pause

    request_pause(job_id)
    await update.message.reply_text(
        f"Pause signal sent for job #{job_id}.\n"
        "Application will pause after the current step.\n"
        f"Resume later with /resume {job_id}"
    )


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resume a paused application."""
    if not _is_authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /resume <job_id>")
        return
    rate_msg = _check_rate_limit(update.effective_user.id)
    if rate_msg:
        await update.message.reply_text(rate_msg)
        return

    try:
        job_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid job ID.")
        return

    init_db()
    from src.db.database import get_pause_state

    pause_state = get_pause_state(job_id)
    if not pause_state:
        await update.message.reply_text(f"Job #{job_id} has no saved pause state.")
        return

    job_data = get_job(job_id)
    app_data = get_application(job_id)
    if not job_data or not app_data:
        await update.message.reply_text(f"Job #{job_id} not found.")
        return

    application_url = job_data.get("application_url") or job_data.get("url", "")
    await update.message.reply_text(
        f"Resuming application for *{_md_escape(job_data['title'])}* at {_md_escape(job_data['company'])}\n"
        f"Paused at step {pause_state['step']}. Reopening browser...",
        parse_mode="Markdown",
    )

    try:
        from src.agent.computer_use import fill_application
        from src.analyzer.job_analyzer import load_master_resume

        master_resume = load_master_resume()

        result = await fill_application(
            application_url=application_url,
            master_resume=master_resume,
            resume_path=app_data["resume_path"],
            cover_letter_path=app_data.get("cover_letter_path", ""),
            job_id=job_id,
            headless=False,
            resume=True,
        )

        if result["status"] == "submitted":
            await update.message.reply_text(f"Application for job #{job_id} submitted!")
        elif result["status"] == "failed":
            reason = result.get("message", "Unknown error")
            await update.message.reply_text(
                f"Application for job #{job_id} failed.\nReason: {reason}"
            )
        elif result["status"] == "paused":
            await update.message.reply_text(
                f"Application paused again at step {result.get('steps_taken', '?')}.\n"
                f"Use /resume {job_id} to continue."
            )
        else:
            await update.message.reply_text(
                f"Application result: {result['status']} ({result.get('steps_taken', 0)} steps)"
            )
    except Exception as e:
        logger.exception("Resume failed for job ID: %d", job_id)
        await update.message.reply_text(f"Resume failed: {e}")


async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show instructions for saving browser login sessions."""
    if not _is_authorized(update):
        return

    from src.scraper.browser_session import list_sessions

    sessions = list_sessions()
    session_list = "\n".join(f"  • {s}" for s in sessions) if sessions else "  None"

    await update.message.reply_text(
        "*Browser Sessions*\n\n"
        "To save a login session, run on your machine:\n"
        "`job login --site linkedin`\n"
        "`job login --site indeed`\n\n"
        "This opens a browser — log in manually, then close it. "
        "Session is saved and reused for future scraping and applications.\n\n"
        f"*Saved sessions:*\n{session_list}",
        parse_mode="Markdown",
    )


async def request_approval(job_id: int, message: str) -> bool:
    """Send an approval request with inline buttons and wait for user response.

    Uses inline keyboard buttons for reliable approval instead of free-text matching.
    Returns True if approved, False if skipped.
    """
    event = asyncio.Event()
    _pending_approvals[job_id] = event
    logger.info("Set pending approval for job %d, dict id=%d, keys=%s", job_id, id(_pending_approvals), list(_pending_approvals.keys()))

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Submit", callback_data=f"approve_{job_id}"),
            InlineKeyboardButton("Skip", callback_data=f"skip_{job_id}"),
        ]
    ])
    token, user_id = _get_config()
    bot = Bot(token=token)
    await bot.send_message(
        chat_id=user_id,
        text=message,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    logger.info("Approval request sent for job %d (waiting for button click)", job_id)
    await event.wait()
    return _approval_results.pop(job_id, False)


async def _handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses for submit/skip approval."""
    query = update.callback_query
    logger.info("Callback received: %s", query.data)
    await query.answer()  # Acknowledge the button press

    data = query.data
    if data.startswith("approve_"):
        job_id = int(data.split("_", 1)[1])
        logger.info("Approve button for job %d, dict id=%d, pending: %s", job_id, id(_pending_approvals), list(_pending_approvals.keys()))
        if job_id in _pending_approvals:
            _approval_results[job_id] = True
            _pending_approvals[job_id].set()
            del _pending_approvals[job_id]
            await query.edit_message_text(f"Approved. Submitting application for job #{job_id}...")
        else:
            await query.edit_message_text("No pending approval for this job.")

    elif data.startswith("skip_"):
        job_id = int(data.split("_", 1)[1])
        if job_id in _pending_approvals:
            _approval_results[job_id] = False
            _pending_approvals[job_id].set()
            del _pending_approvals[job_id]
            await query.edit_message_text(f"Skipped application for job #{job_id}.")
        else:
            await query.edit_message_text("No pending approval for this job.")


def run_bot() -> None:
    """Start the Telegram bot (blocking)."""
    token, _ = _get_config()
    app = Application.builder().token(token).build()

    # Browse commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(CommandHandler("jobs", cmd_jobs))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("job", cmd_job))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("analytics", cmd_analytics))
    app.add_handler(CommandHandler("skills", cmd_skills))
    app.add_handler(CommandHandler("calibrate", cmd_calibrate))
    app.add_handler(CommandHandler("login", cmd_login))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))

    # Action commands
    app.add_handler(CommandHandler("discover", cmd_discover))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("linkedin", cmd_linkedin))
    app.add_handler(CommandHandler("scrape", cmd_scrape))
    app.add_handler(CommandHandler("paste", cmd_paste))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("collect", cmd_collect))
    app.add_handler(CommandHandler("review", cmd_review))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("reject", cmd_reject))
    app.add_handler(CommandHandler("generate", cmd_generate))
    app.add_handler(CommandHandler("apply", cmd_apply))
    app.add_handler(CommandHandler("send", cmd_send))
    app.add_handler(CommandHandler("update", cmd_update_status))

    # Inline button callbacks (approval flow)
    app.add_handler(CallbackQueryHandler(_handle_approval_callback))

    # Free text: paste mode + approval flow (fallback for text replies)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    logger.info("Telegram bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    import sys

    # Ensure both __main__ and src.agent.telegram_bot point to the same module.
    # Without this, imports from other modules (e.g. computer_use.py) create a
    # second module instance with separate global state (_pending_approvals, etc.)
    sys.modules["src.agent.telegram_bot"] = sys.modules["__main__"]

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent.parent.parent / ".env")

    from src.logging_config import setup_logging

    setup_logging()
    run_bot()
