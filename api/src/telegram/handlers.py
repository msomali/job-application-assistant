"""Telegram command handlers — adapted from core/src/agent/telegram_bot.py for SaaS."""

import logging

import redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models import Analysis, Application, Job, TelegramAccount, User
from src.db.models import Task as TaskModel
from src.db.pg import set_tenant_context
from src.telegram.sender import send_inline_keyboard, send_text

logger = logging.getLogger(__name__)

HEAVY_CMD_COOLDOWN = 30  # seconds


def _md_escape(text) -> str:
    """Escape Telegram Markdown special characters."""
    if text is None:
        return "N/A"
    text = str(text)
    for ch in "_*`[":
        text = text.replace(ch, f"\\{ch}")
    return text


async def _get_user_for_chat(session: AsyncSession, chat_id: int) -> tuple[TelegramAccount | None, User | None]:
    """Look up linked Telegram account and user by chat_id."""
    result = await session.execute(
        select(TelegramAccount).where(TelegramAccount.chat_id == chat_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        return None, None
    user_result = await session.execute(select(User).where(User.id == account.user_id))
    user = user_result.scalar_one_or_none()
    return account, user


def _check_rate_limit(chat_id: int) -> str | None:
    """Check rate limit for heavy commands using Redis TTL keys."""
    try:
        r = redis.from_url(settings.redis_url)
        key = f"telegram:rate:{chat_id}"
        if r.exists(key):
            ttl = r.ttl(key)
            return f"Please wait {ttl}s before running another heavy command."
        r.setex(key, HEAVY_CMD_COOLDOWN, "1")
        return None
    except Exception:
        return None


async def handle_command(session: AsyncSession, chat_id: int, text: str, update: dict) -> None:
    """Dispatch a command to the appropriate handler."""
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower().split("@")[0]  # Strip @botname suffix
    args = parts[1] if len(parts) > 1 else ""

    account, user = await _get_user_for_chat(session, chat_id)
    if not account or not user:
        await send_text(chat_id, "Please link your account first — visit Settings in the web app.")
        return

    await set_tenant_context(session, str(user.tenant_id))

    handlers = {
        "/help": _cmd_help,
        "/jobs": _cmd_jobs,
        "/top": _cmd_top,
        "/job": _cmd_job,
        "/discover": _cmd_discover,
        "/search": _cmd_search,
        "/generate": _cmd_generate,
        "/approve": _cmd_approve,
        "/status": _cmd_status,
        "/unlink": _cmd_unlink,
    }

    handler = handlers.get(cmd)
    if handler:
        await handler(session, chat_id, user, args)
    else:
        await send_text(chat_id, f"Unknown command: {cmd}. Type /help for available commands.")


async def handle_callback(session: AsyncSession, chat_id: int, data: str) -> None:
    """Handle inline keyboard callback queries."""
    account, user = await _get_user_for_chat(session, chat_id)
    if not account or not user:
        return

    await set_tenant_context(session, str(user.tenant_id))

    # Parse callback data: "action:job_id"
    parts = data.split(":")
    if len(parts) < 2:
        return

    action, job_id_str = parts[0], parts[1]
    try:
        job_id = int(job_id_str)
    except ValueError:
        return

    if action == "analyze":
        await _cmd_analyze_job(session, chat_id, user, job_id)
    elif action == "generate":
        await _cmd_generate(session, chat_id, user, str(job_id))
    elif action == "detail":
        await _cmd_job(session, chat_id, user, str(job_id))


async def _cmd_help(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    help_text = (
        "*Available Commands:*\n\n"
        "/jobs — Latest 10 jobs with scores\n"
        "/top — Jobs with fit score >= 70\n"
        "/job <id> — Job details\n"
        "/discover — Run job discovery\n"
        "/search <query> — Search for jobs\n"
        "/generate <id> — Generate resume + cover letter\n"
        "/approve <ids> — Approve jobs for application\n"
        "/status — Application pipeline summary\n"
        "/unlink — Disconnect Telegram\n"
        "/help — Show this message"
    )
    await send_text(chat_id, help_text)


async def _cmd_jobs(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    result = await session.execute(
        select(Job).order_by(Job.scraped_at.desc()).limit(10)
    )
    jobs = result.scalars().all()
    if not jobs:
        await send_text(chat_id, "No jobs found. Try /discover or /search first.")
        return

    lines = ["*Latest Jobs:*\n"]
    for j in jobs:
        analysis_result = await session.execute(
            select(Analysis.fit_score).where(Analysis.job_id == j.id).order_by(Analysis.analyzed_at.desc()).limit(1)
        )
        score = analysis_result.scalar_one_or_none()
        score_str = f" ({score}%)" if score else ""
        lines.append(f"#{j.id} {_md_escape(j.title)} @ {_md_escape(j.company)}{score_str}")

    await send_text(chat_id, "\n".join(lines))


async def _cmd_top(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    result = await session.execute(
        select(Job, Analysis.fit_score)
        .join(Analysis, Analysis.job_id == Job.id)
        .where(Analysis.fit_score >= 70)
        .order_by(Analysis.fit_score.desc())
        .limit(10)
    )
    rows = result.all()
    if not rows:
        await send_text(chat_id, "No jobs with fit score >= 70 yet.")
        return

    lines = ["*Top Matches (70%+):*\n"]
    for job, score in rows:
        lines.append(f"#{job.id} {_md_escape(job.title)} @ {_md_escape(job.company)} — *{score}%*")

    await send_text(chat_id, "\n".join(lines))


async def _cmd_job(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    if not args:
        await send_text(chat_id, "Usage: /job <id>")
        return
    try:
        job_id = int(args.strip())
    except ValueError:
        await send_text(chat_id, "Invalid job ID. Usage: /job <id>")
        return

    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        await send_text(chat_id, f"Job #{job_id} not found.")
        return

    analysis_result = await session.execute(
        select(Analysis).where(Analysis.job_id == job_id).order_by(Analysis.analyzed_at.desc()).limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()

    text = f"*{_md_escape(job.title)}*\n{_md_escape(job.company)}"
    if job.location:
        text += f"\n{_md_escape(job.location)}"
    if job.salary_range:
        text += f"\nSalary: {_md_escape(job.salary_range)}"
    if analysis:
        text += f"\n\nFit Score: *{analysis.fit_score}%*"
        if analysis.matching_skills:
            text += f"\nMatching: {', '.join(_md_escape(s) for s in analysis.matching_skills[:5])}"
        if analysis.gaps:
            text += f"\nGaps: {', '.join(_md_escape(g) for g in analysis.gaps[:5])}"

    buttons = [
        [("Analyze", f"analyze:{job_id}"), ("Generate Docs", f"generate:{job_id}")],
    ]
    await send_inline_keyboard(chat_id, text, buttons)


async def _cmd_discover(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    rate_msg = _check_rate_limit(chat_id)
    if rate_msg:
        await send_text(chat_id, rate_msg)
        return

    task = TaskModel(
        tenant_id=user.tenant_id,
        user_id=user.id,
        type="discover",
        status="pending",
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    from src.workers.tasks import run_discovery
    run_discovery.delay(str(task.id), str(user.tenant_id))

    await send_text(chat_id, "Discovery started. I'll notify you when it completes.")


async def _cmd_search(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    if not args:
        await send_text(chat_id, "Usage: /search <query>")
        return

    rate_msg = _check_rate_limit(chat_id)
    if rate_msg:
        await send_text(chat_id, rate_msg)
        return

    await send_text(chat_id, f"Searching for: {_md_escape(args)}...")


async def _cmd_generate(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    if not args:
        await send_text(chat_id, "Usage: /generate <job_id>")
        return
    try:
        job_id = int(args.strip())
    except ValueError:
        await send_text(chat_id, "Invalid job ID.")
        return

    rate_msg = _check_rate_limit(chat_id)
    if rate_msg:
        await send_text(chat_id, rate_msg)
        return

    task = TaskModel(
        tenant_id=user.tenant_id,
        user_id=user.id,
        type="generate",
        status="pending",
        input={"job_id": job_id},
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    from src.workers.tasks import generate_docs
    generate_docs.delay(str(task.id), str(user.tenant_id), job_id)

    await send_text(chat_id, f"Generating docs for job #{job_id}. I'll send them when ready.")


async def _cmd_analyze_job(session: AsyncSession, chat_id: int, user: User, job_id: int) -> None:
    task = TaskModel(
        tenant_id=user.tenant_id,
        user_id=user.id,
        type="analyze",
        status="pending",
        input={"job_id": job_id},
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    from src.workers.tasks import analyze_job
    analyze_job.delay(str(task.id), str(user.tenant_id), job_id)

    await send_text(chat_id, f"Analyzing job #{job_id}...")


async def _cmd_approve(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    if not args:
        await send_text(chat_id, "Usage: /approve <id1> <id2> ...")
        return
    ids = []
    for s in args.split():
        try:
            ids.append(int(s))
        except ValueError:
            pass
    if not ids:
        await send_text(chat_id, "No valid job IDs provided.")
        return

    updated = 0
    for job_id in ids:
        result = await session.execute(
            select(Application).where(Application.job_id == job_id)
        )
        app = result.scalar_one_or_none()
        if app:
            app.status = "approved"
            updated += 1

    await session.commit()
    await send_text(chat_id, f"Approved {updated} job(s).")


async def _cmd_status(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    result = await session.execute(
        select(Application.status, func.count()).group_by(Application.status)
    )
    rows = result.all()
    if not rows:
        await send_text(chat_id, "No applications tracked yet.")
        return

    lines = ["*Application Pipeline:*\n"]
    for status, count in rows:
        lines.append(f"  {status}: {count}")
    await send_text(chat_id, "\n".join(lines))


async def _cmd_unlink(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    from src.telegram.linking import unlink_telegram
    success = await unlink_telegram(session, str(user.id))
    if success:
        await send_text(chat_id, "Telegram account unlinked. You won't receive notifications here anymore.")
    else:
        await send_text(chat_id, "No linked account found.")
