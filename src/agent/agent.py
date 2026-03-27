"""Autonomous job application agent using Claude Agent SDK."""

import asyncio
import json
import logging
import sys
from datetime import UTC
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    create_sdk_mcp_server,
    query,
    tool,
)

from src.agent.computer_use import fill_application
from src.analyzer.job_analyzer import analyze_job, load_master_resume
from src.db.database import (
    get_analysis,
    get_job,
    init_db,
    list_jobs,
    save_analysis,
    save_job,
    update_application,
)
from src.generator.cover_letter_generator import (
    generate_cover_letter_content,
    render_cover_letter,
)
from src.generator.resume_generator import generate_resume_content, render_resume
from src.models import JobAnalysis, JobPosting
from src.scraper.firecrawl_client import _extract_with_claude, scrape_job
from src.scraper.job_discovery import discover_all, scrape_search_result, search_jobs

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"


# --- Tool definitions ---


@tool(
    "discover_jobs",
    "Run all configured job searches and career page crawls. Returns a list of newly discovered jobs with their IDs.",
    {},
)
async def tool_discover_jobs(args: dict[str, Any]) -> dict[str, Any]:
    init_db()
    results = discover_all()
    new_jobs = []

    for result in results:
        url = result["url"]
        markdown = result.get("markdown", "")
        if not markdown.strip():
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

    logger.info("tool_discover_jobs found %d jobs", len(new_jobs))
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {"jobs_found": len(new_jobs), "jobs": new_jobs}, indent=2
                ),
            }
        ]
    }


@tool(
    "search_and_analyze",
    "Search the web for jobs matching a query, scrape each result, and analyze fit.",
    {"query": str, "limit": int},
)
async def tool_search_and_analyze(args: dict[str, Any]) -> dict[str, Any]:
    init_db()
    query_str = args["query"]
    limit = args.get("limit", 5)

    results = search_jobs(query_str, limit=limit)
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

    logger.info("tool_search_and_analyze found %d jobs for query: %s", len(new_jobs), query_str)
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {"query": query_str, "jobs_found": len(new_jobs), "jobs": new_jobs},
                    indent=2,
                ),
            }
        ]
    }


@tool(
    "scrape_and_analyze_url",
    "Scrape a single job URL, extract job details, analyze fit, and store in database.",
    {"url": str},
)
async def tool_scrape_and_analyze(args: dict[str, Any]) -> dict[str, Any]:
    init_db()
    url = args["url"]
    job, raw_markdown = scrape_job(url)
    job_id = save_job(job.model_dump(), url, raw_markdown)
    analysis = analyze_job(job)
    save_analysis(job_id, analysis.model_dump())

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "job_id": job_id,
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "fit_score": analysis.fit_score,
                        "matching_skills": analysis.matching_skills,
                        "gaps": analysis.gaps,
                        "strategy": analysis.tailoring_strategy,
                    },
                    indent=2,
                ),
            }
        ]
    }


@tool(
    "generate_documents",
    "Generate a tailored resume and cover letter PDF for a job. Returns file paths.",
    {"job_id": int},
)
async def tool_generate_documents(args: dict[str, Any]) -> dict[str, Any]:
    init_db()
    job_id = args["job_id"]

    job_data = get_job(job_id)
    if not job_data:
        return {"content": [{"type": "text", "text": f"Job {job_id} not found."}]}

    analysis_data = get_analysis(job_id)
    if not analysis_data:
        return {
            "content": [
                {"type": "text", "text": f"No analysis for job {job_id}. Analyze first."}
            ]
        }

    job = JobPosting(**job_data)
    analysis = JobAnalysis(**analysis_data)
    master_resume = load_master_resume()

    import re
    from datetime import datetime

    slug = re.sub(r"[^a-z0-9]+", "-", f"{job.company}-{job.title}".lower()).strip("-")[
        :40
    ]
    date_str = datetime.now(UTC).strftime("%Y%m%d")
    output_dir = OUTPUT_DIR / f"{slug}_{date_str}_{job_id}"

    resume_content = generate_resume_content(job, analysis, master_resume)
    resume_pdf = render_resume(resume_content, master_resume, output_dir)
    update_application(job_id, resume_path=str(resume_pdf))

    cover_letter_content = generate_cover_letter_content(job, analysis, master_resume)
    cover_letter_pdf = render_cover_letter(
        cover_letter_content, master_resume, output_dir
    )
    update_application(job_id, cover_letter_path=str(cover_letter_pdf), status="docs_generated")

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "job_id": job_id,
                        "resume_pdf": str(resume_pdf),
                        "cover_letter_pdf": str(cover_letter_pdf),
                    },
                    indent=2,
                ),
            }
        ]
    }


@tool(
    "list_top_jobs",
    "List top-ranked jobs by fit score. Returns jobs above the minimum score threshold.",
    {"min_score": int, "limit": int},
)
async def tool_list_top_jobs(args: dict[str, Any]) -> dict[str, Any]:
    init_db()
    min_score = args.get("min_score", 60)
    limit = args.get("limit", 10)

    jobs = list_jobs(limit=100)
    top = [j for j in jobs if j.get("fit_score") and j["fit_score"] >= min_score]
    top.sort(key=lambda j: j["fit_score"], reverse=True)
    top = top[:limit]

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(top, indent=2, default=str),
            }
        ]
    }


@tool(
    "notify_user",
    "Send a notification message to the user via Telegram.",
    {"message": str},
)
async def tool_notify_user(args: dict[str, Any]) -> dict[str, Any]:
    from src.agent.telegram_bot import send_notification

    await send_notification(args["message"])
    return {"content": [{"type": "text", "text": "Notification sent."}]}


@tool(
    "send_document_to_user",
    "Send a PDF document to the user via Telegram.",
    {"file_path": str, "caption": str},
)
async def tool_send_document(args: dict[str, Any]) -> dict[str, Any]:
    from src.agent.telegram_bot import send_document

    await send_document(args["file_path"], args.get("caption", ""))
    return {"content": [{"type": "text", "text": "Document sent."}]}


@tool(
    "request_user_approval",
    "Ask the user for approval before taking an action. Blocks until user responds.",
    {"job_id": int, "message": str},
)
async def tool_request_approval(args: dict[str, Any]) -> dict[str, Any]:
    from src.agent.telegram_bot import request_approval

    approved = await request_approval(args["job_id"], args["message"])
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps({"approved": approved}),
            }
        ]
    }


@tool(
    "apply_to_job",
    "Fill out and submit a job application using browser automation. "
    "Requires that documents have been generated first (generate_documents). "
    "The agent will fill the form, send a screenshot for review, and wait for user approval before submitting.",
    {"job_id": int},
)
async def tool_apply_to_job(args: dict[str, Any]) -> dict[str, Any]:
    init_db()
    job_id = args["job_id"]

    job_data = get_job(job_id)
    if not job_data:
        return {"content": [{"type": "text", "text": f"Job {job_id} not found."}]}

    analysis_data = get_analysis(job_id)
    if not analysis_data:
        return {
            "content": [
                {"type": "text", "text": f"No analysis for job {job_id}. Analyze first."}
            ]
        }

    # Check that documents exist
    from src.db.database import get_application
    app_data = get_application(job_id)
    if not app_data or not app_data.get("resume_path"):
        return {
            "content": [
                {"type": "text", "text": f"No documents for job {job_id}. Run generate_documents first."}
            ]
        }

    application_url = job_data.get("application_url") or job_data.get("url", "")
    if not application_url:
        return {
            "content": [
                {"type": "text", "text": f"No application URL for job {job_id}."}
            ]
        }

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
        update_application(job_id, status="applied")

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "job_id": job_id,
                        "status": result["status"],
                        "steps_taken": result.get("steps_taken", 0),
                        "message": result.get("message", ""),
                    },
                    indent=2,
                ),
            }
        ]
    }


# --- Agent setup ---


def create_tools_server():
    """Create the MCP tools server with all job application tools."""
    return create_sdk_mcp_server(
        name="job-assistant",
        version="1.0.0",
        tools=[
            tool_discover_jobs,
            tool_search_and_analyze,
            tool_scrape_and_analyze,
            tool_generate_documents,
            tool_list_top_jobs,
            tool_notify_user,
            tool_send_document,
            tool_request_approval,
            tool_apply_to_job,
        ],
    )


SYSTEM_PROMPT = """\
You are a Job Application Assistant agent. Your job is to help the user find, analyze, and apply to jobs.

You have the following tools:
- discover_jobs: Run all configured searches and crawls to find new jobs
- search_and_analyze: Search for jobs with a specific query
- scrape_and_analyze_url: Scrape and analyze a single job URL
- generate_documents: Generate a tailored resume and cover letter for a job
- list_top_jobs: List top-ranked jobs by fit score
- notify_user: Send a Telegram notification to the user
- send_document_to_user: Send a PDF to the user via Telegram
- request_user_approval: Ask the user for approval before an action
- apply_to_job: Fill out and submit a job application via browser automation (requires docs generated first)

Workflow:
1. When asked to find jobs, use discover_jobs or search_and_analyze
2. Present top matches to the user (via notify_user if running autonomously)
3. When asked to generate docs, use generate_documents and send_document_to_user
4. When asked to apply, first generate_documents, then apply_to_job
5. apply_to_job will automatically request user approval before final submission
6. Be proactive about identifying the best matches and explaining why

Be concise in your responses. Focus on actionable information.
"""


async def run_agent(prompt: str) -> None:
    """Run the agent with a given prompt."""
    tools_server = create_tools_server()

    options = ClaudeAgentOptions(
        mcp_servers={"job-assistant": tools_server},
        allowed_tools=[
            "mcp__job-assistant__discover_jobs",
            "mcp__job-assistant__search_and_analyze",
            "mcp__job-assistant__scrape_and_analyze_url",
            "mcp__job-assistant__generate_documents",
            "mcp__job-assistant__list_top_jobs",
            "mcp__job-assistant__notify_user",
            "mcp__job-assistant__send_document_to_user",
            "mcp__job-assistant__request_user_approval",
            "mcp__job-assistant__apply_to_job",
        ],
        system_prompt=SYSTEM_PROMPT,
    )

    logger.info("Running agent with prompt: %s", prompt[:100])
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, "text"):
                    logger.info("Agent response: %s", block.text[:200])
                elif hasattr(block, "name"):
                    logger.info("Agent tool call: %s", block.name)
        elif isinstance(message, ResultMessage):
            if message.subtype == "error":
                logger.error("Agent error: %s", message.error)


async def run_daily_pipeline() -> None:
    """Run the full daily pipeline: discover, analyze, notify."""
    await run_agent(
        "Discover new jobs using the configured searches and crawls. "
        "Analyze all discovered jobs. "
        "Then notify the user via Telegram with the top 5 matches (fit score >= 70). "
        "Include job title, company, location, and fit score in the notification."
    )


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent.parent.parent / ".env")

    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        prompt = input("What would you like to do? ")

    asyncio.run(run_agent(prompt))
