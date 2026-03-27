"""CLI entry point for the Job Application Assistant."""

import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from src.logging_config import setup_logging

setup_logging()

logger = logging.getLogger(__name__)

import click

from src.analyzer.job_analyzer import analyze_job, load_master_resume
from src.db.database import (
    delete_answer,
    find_answer_fuzzy,
    get_analysis,
    get_answer_stats,
    get_job,
    get_score_calibration,
    get_skill_gaps,
    get_skill_stats,
    get_skill_stats_by_role,
    get_skill_trend,
    import_screening_answers,
    init_db,
    list_answers,
    list_jobs,
    save_analysis,
    save_answer,
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
from src.scraper.job_discovery import (
    crawl_career_page,
    discover_all,
    scrape_search_result,
    search_jobs,
)

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def _validate_url(url: str) -> str:
    """Validate that a URL is safe to scrape."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise click.BadParameter(f"Invalid URL scheme: {parsed.scheme}. Only http/https allowed.")
    if not parsed.netloc:
        raise click.BadParameter("Invalid URL: missing domain.")
    return url


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


@click.group()
def cli():
    """Job Application Assistant — scrape, analyze, generate."""
    init_db()


@cli.command()
@click.argument("url")
@click.option("--no-redact", is_flag=True, help="Disable PII redaction for LLM calls (debug only)")
def scrape(url: str, no_redact: bool):
    """Scrape a job URL, analyze it, and generate tailored resume + cover letter."""
    redact = not no_redact
    url = _validate_url(url)
    click.echo(f"Scraping: {url}")
    logger.info("Scraping URL: %s", url)
    job, raw_markdown = scrape_job(url)
    click.echo(f"  → {job.title} at {job.company} ({job.location})")
    logger.info("Scraped job: %s at %s (%s)", job.title, job.company, job.location)

    job_id = save_job(job.model_dump(), url, raw_markdown)
    click.echo(f"  → Saved to database (ID: {job_id})")
    logger.info("Job saved to database with ID: %d", job_id)

    click.echo("Analyzing fit...")
    if redact:
        click.echo("  → PII redaction: enabled")
    logger.info("Analyzing fit for job ID: %d", job_id)
    analysis = analyze_job(job, redact=redact)
    save_analysis(job_id, analysis.model_dump())
    if analysis.base_score is not None:
        click.echo(f"  → Base score: {analysis.base_score}/100")
    click.echo(f"  → Fit score: {analysis.fit_score}/100")
    if analysis.penalties:
        for p in analysis.penalties:
            sign = "+" if p.points > 0 else ""
            click.echo(f"    {sign}{p.points}  {p.rule}: {p.reason}")
    logger.info("Fit score for job ID %d: %d/100", job_id, analysis.fit_score)
    click.echo(f"  → Matching: {', '.join(analysis.matching_skills[:5])}")
    if analysis.gaps:
        click.echo(f"  → Gaps: {', '.join(analysis.gaps[:3])}")

    click.echo("Generating resume and cover letter...")
    logger.info("Generating documents for job ID: %d", job_id)
    master_resume = load_master_resume()
    _generate_docs(job, analysis, master_resume, job_id, redact=redact)

    update_application(job_id, status="docs_generated")
    click.echo("Done!")
    logger.info("Scrape pipeline complete for job ID: %d", job_id)


@cli.command()
@click.argument("job_id", type=int)
def analyze(job_id: int):
    """Re-analyze a stored job posting."""
    job_data = get_job(job_id)
    if not job_data:
        click.echo(f"Job {job_id} not found.")
        logger.warning("Analyze requested for non-existent job ID: %d", job_id)
        return

    job = JobPosting(**job_data)
    click.echo(f"Analyzing: {job.title} at {job.company}")
    logger.info("Re-analyzing job ID %d: %s at %s", job_id, job.title, job.company)

    analysis = analyze_job(job)
    save_analysis(job_id, analysis.model_dump())

    click.echo(f"  → Fit score: {analysis.fit_score}/100")
    logger.info("Re-analysis complete for job ID %d, fit score: %d", job_id, analysis.fit_score)
    click.echo(f"  → Strategy: {analysis.tailoring_strategy}")


@cli.command()
@click.argument("job_id", type=int)
def generate(job_id: int):
    """Re-generate resume and cover letter for a stored job."""
    job_data = get_job(job_id)
    if not job_data:
        click.echo(f"Job {job_id} not found.")
        logger.warning("Generate requested for non-existent job ID: %d", job_id)
        return

    analysis_data = get_analysis(job_id)
    if not analysis_data:
        click.echo(f"No analysis found for job {job_id}. Run 'analyze {job_id}' first.")
        logger.warning("No analysis found for job ID: %d", job_id)
        return

    job = JobPosting(**job_data)
    analysis = JobAnalysis(**analysis_data)
    master_resume = load_master_resume()

    click.echo(f"Generating docs for: {job.title} at {job.company}")
    logger.info("Generating docs for job ID %d: %s at %s", job_id, job.title, job.company)
    _generate_docs(job, analysis, master_resume, job_id)

    update_application(job_id, status="docs_generated")
    click.echo("Done!")
    logger.info("Document generation complete for job ID: %d", job_id)


@cli.command("list")
@click.option("--limit", default=20, help="Number of jobs to show")
def list_cmd(limit: int):
    """List all scraped jobs with fit scores."""
    jobs = list_jobs(limit)
    if not jobs:
        click.echo("No jobs found. Run 'scrape <url>' to add one.")
        return

    click.echo(f"{'ID':>4}  {'Score':>5}  {'Status':<15}  {'Title':<30}  {'Company':<20}")
    click.echo("-" * 80)
    for j in jobs:
        score = str(j.get("fit_score") or "-")
        status = j.get("status") or "discovered"
        click.echo(
            f"{j['id']:>4}  {score:>5}  {status:<15}  "
            f"{j['title'][:30]:<30}  {j['company'][:20]:<20}"
        )


@cli.command()
@click.argument("query")
@click.option("--limit", default=5, help="Number of results per query")
@click.option("--analyze-all", is_flag=True, help="Analyze all discovered jobs")
def search(query: str, limit: int, analyze_all: bool):
    """Search the web for jobs matching a query."""
    click.echo(f"Searching: {query}")
    logger.info("Searching for jobs: %s (limit=%d)", query, limit)
    results = search_jobs(query, limit=limit)
    click.echo(f"Found {len(results)} results")
    logger.info("Search returned %d results for query: %s", len(results), query)

    for result in results:
        url = result["url"]
        click.echo(f"  Scraping: {result.get('title', url)}")

        markdown = scrape_search_result(url)
        if not markdown:
            continue

        try:
            extracted = _extract_with_claude(markdown)
            job = JobPosting(**extracted)
        except Exception as e:
            click.echo(f"  Skipping (parse error): {url} - {e}")
            logger.warning("Parse error for %s: %s", url, e)
            continue

        job_id = save_job(job.model_dump(), url, markdown)
        click.echo(f"  [{job_id}] {job.title} at {job.company} ({job.location})")

        if analyze_all:
            analysis = analyze_job(job)
            save_analysis(job_id, analysis.model_dump())
            click.echo(f"       Fit: {analysis.fit_score}/100")

    click.echo("Done!")


@cli.command()
@click.argument("url")
@click.option("--limit", default=20, help="Max pages to crawl")
@click.option("--include", multiple=True, help="URL path patterns to include")
@click.option("--analyze-all", is_flag=True, help="Analyze all discovered jobs")
def crawl(url: str, limit: int, include: tuple, analyze_all: bool):
    """Crawl a company career page for job listings."""
    click.echo(f"Crawling: {url}")
    logger.info("Crawling career page: %s (limit=%d)", url, limit)
    include_paths = list(include) if include else None
    results = crawl_career_page(url, include_paths=include_paths, limit=limit)
    click.echo(f"Found {len(results)} pages")

    for result in results:
        page_url = result["url"]
        markdown = result.get("markdown", "")

        if not markdown.strip():
            click.echo(f"  Skipping (no content): {page_url}")
            continue

        try:
            extracted = _extract_with_claude(markdown)
            job = JobPosting(**extracted)
        except Exception as e:
            click.echo(f"  Skipping (not a job page): {page_url}")
            logger.debug("Not a job page %s: %s", page_url, e)
            continue

        job_id = save_job(job.model_dump(), page_url, markdown)
        click.echo(f"  [{job_id}] {job.title} at {job.company} ({job.location})")

        if analyze_all:
            analysis = analyze_job(job)
            save_analysis(job_id, analysis.model_dump())
            click.echo(f"       Fit: {analysis.fit_score}/100")

    click.echo("Done!")


@cli.command()
@click.option("--analyze-all", is_flag=True, help="Analyze all discovered jobs")
def discover(analyze_all: bool):
    """Run all configured searches and crawls from search_config.json."""
    click.echo("Running full job discovery...")
    logger.info("Starting full job discovery")
    results = discover_all()
    click.echo(f"\nDiscovered {len(results)} unique job pages. Extracting...")
    logger.info("Discovered %d unique job pages", len(results))

    processed = 0
    for result in results:
        url = result["url"]
        markdown = result.get("markdown", "")

        if not markdown.strip():
            continue

        try:
            extracted = _extract_with_claude(markdown)
            job = JobPosting(**extracted)
        except Exception as e:
            click.echo(f"  Skipping (not a job page): {url}")
            logger.debug("Not a job page %s: %s", url, e)
            continue

        job_id = save_job(job.model_dump(), url, markdown)
        click.echo(f"  [{job_id}] {job.title} at {job.company} ({job.location})")
        processed += 1

        if analyze_all:
            analysis = analyze_job(job)
            save_analysis(job_id, analysis.model_dump())
            click.echo(f"       Fit: {analysis.fit_score}/100")

    click.echo(f"\nProcessed {processed} jobs. Run 'list' to see results.")


@cli.command()
@click.option("--min-score", default=60, help="Minimum fit score to show")
@click.option("--limit", default=20, help="Number of jobs to show")
def rank(min_score: int, limit: int):
    """Show jobs ranked by fit score, filtered by minimum score."""
    jobs = list_jobs(limit=100)
    ranked = [j for j in jobs if j.get("fit_score") and j["fit_score"] >= min_score]
    ranked.sort(key=lambda j: j["fit_score"], reverse=True)
    ranked = ranked[:limit]

    if not ranked:
        click.echo(f"No jobs with fit score >= {min_score}. Run 'discover --analyze-all' first.")
        return

    click.echo(f"{'ID':>4}  {'Score':>5}  {'Status':<15}  {'Title':<30}  {'Company':<20}")
    click.echo("-" * 80)
    for j in ranked:
        status = j.get("status") or "discovered"
        click.echo(
            f"{j['id']:>4}  {j['fit_score']:>5}  {status:<15}  "
            f"{j['title'][:30]:<30}  {j['company'][:20]:<20}"
        )


@cli.group()
def skills():
    """Skill market analytics — see what the market demands."""
    pass


@skills.command("top")
@click.option("--limit", default=30, help="Number of skills to show")
def skills_top(limit: int):
    """Show most in-demand skills across all discovered jobs."""
    stats = get_skill_stats(limit)
    if not stats:
        click.echo("No skill data yet. Run 'discover --analyze-all' to populate.")
        return

    click.echo(f"\n{'Rank':>4}  {'Skill':<35}  {'Jobs':>5}  {'Sources'}")
    click.echo("-" * 70)
    for i, s in enumerate(stats, 1):
        click.echo(f"{i:>4}  {s['skill']:<35}  {s['job_count']:>5}  {s['sources']}")


@skills.command("roles")
@click.option("--limit", default=15, help="Skills per role")
def skills_by_role(limit: int):
    """Show top skills broken down by role type."""
    by_role = get_skill_stats_by_role(limit)
    if not by_role:
        click.echo("No skill data yet. Run 'discover --analyze-all' to populate.")
        return

    for role, role_skills in by_role.items():
        click.echo(f"\n  {role}")
        click.echo(f"  {'─' * 50}")
        for i, s in enumerate(role_skills, 1):
            click.echo(f"  {i:>3}. {s['skill']:<35} ({s['job_count']} jobs)")


@skills.command("trends")
@click.option("--days", default=30, help="Cutoff in days for recent vs older")
def skills_trends(days: int):
    """Show rising and established skills (recent vs older jobs)."""
    trend = get_skill_trend(days)

    if trend["rising"]:
        click.echo(f"\n  Rising Skills (more common in last {days} days)")
        click.echo(f"  {'─' * 55}")
        click.echo(f"  {'Skill':<35}  {'Recent':>7}  {'Older':>7}")
        for s in trend["rising"]:
            delta = f"+{s['recent'] - s['older']}"
            click.echo(f"  {s['skill']:<35}  {s['recent']:>7}  {s['older']:>7}  {delta}")
    else:
        click.echo(f"\nNo rising skill trends yet (need jobs scraped across {days}+ day span).")

    if trend["established"]:
        click.echo(f"\n  Established Skills (consistently in demand)")
        click.echo(f"  {'─' * 55}")
        click.echo(f"  {'Skill':<35}  {'Recent':>7}  {'Older':>7}")
        for s in trend["established"]:
            click.echo(f"  {s['skill']:<35}  {s['recent']:>7}  {s['older']:>7}")


@skills.command("gaps")
@click.option("--limit", default=20, help="Number of gaps to show")
def skills_gaps(limit: int):
    """Show in-demand skills you're missing (compared to your master resume)."""
    master_resume = load_master_resume()
    user_skills = master_resume.get("skills", [])

    gaps = get_skill_gaps(user_skills, limit)
    if not gaps:
        click.echo("No skill gaps found — either you have everything or no data yet.")
        return

    click.echo(f"\n  Skills the market wants that you don't list")
    click.echo(f"  {'─' * 50}")
    click.echo(f"  {'Skill':<35}  {'Jobs Requiring':>14}")
    for g in gaps:
        click.echo(f"  {g['skill']:<35}  {g['job_count']:>14}")
    click.echo(f"\n  Tip: Consider adding these to your master_resume.json if you have them.")


@cli.group()
def answers():
    """Answer cache — manage screening question answers."""
    pass


@answers.command("list")
@click.option("--category", default=None, help="Filter by category")
@click.option("--source", default=None, help="Filter by source (manual/imported/llm)")
@click.option("--limit", default=30, help="Number of answers to show")
def answers_list(category: str | None, source: str | None, limit: int):
    """List cached screening answers."""
    cached = list_answers(category=category, source=source, limit=limit)
    if not cached:
        click.echo("No cached answers. Run 'answers import' to import from screening_answers.json.")
        return

    click.echo(f"\n{'ID':>4}  {'Uses':>4}  {'Source':<9}  {'Category':<18}  {'Question':<35}  {'Answer'}")
    click.echo("-" * 110)
    for a in cached:
        q = a["question"][:33] + ".." if len(a["question"]) > 35 else a["question"]
        ans = str(a["answer"])[:40] + ".." if len(str(a["answer"])) > 42 else str(a["answer"])
        cat = (a["category"] or "-")[:18]
        click.echo(f"{a['id']:>4}  {a['times_used']:>4}  {a['source']:<9}  {cat:<18}  {q:<35}  {ans}")


@answers.command("search")
@click.argument("question")
def answers_search(question: str):
    """Search for a cached answer (supports fuzzy matching)."""
    result = find_answer_fuzzy(question)
    if result:
        fuzzy = f" (fuzzy: {result['_fuzzy_score']:.0%})" if "_fuzzy_score" in result else ""
        click.echo(f"\nMatch found{fuzzy}:")
        click.echo(f"  Question: {result['question']}")
        click.echo(f"  Answer:   {result['answer']}")
        click.echo(f"  Source:   {result['source']}")
        click.echo(f"  Used:     {result['times_used']} times")
    else:
        click.echo(f"No match found for: {question}")


@answers.command("add")
@click.argument("question")
@click.argument("answer")
@click.option("--category", default=None, help="Category (e.g., personal, experience)")
def answers_add(question: str, answer: str, category: str | None):
    """Add or update a cached answer."""
    answer_id = save_answer(question, answer, source="manual", category=category)
    click.echo(f"Saved answer ID {answer_id}: {question[:50]} -> {answer[:50]}")


@answers.command("delete")
@click.argument("answer_id", type=int)
def answers_delete(answer_id: int):
    """Delete a cached answer by ID."""
    if delete_answer(answer_id):
        click.echo(f"Deleted answer ID {answer_id}.")
    else:
        click.echo(f"Answer ID {answer_id} not found.")


@answers.command("import")
def answers_import():
    """Import answers from screening_answers.json into the cache."""
    screening_path = Path(__file__).parent.parent / "data" / "screening_answers.json"
    count = import_screening_answers(screening_path)
    click.echo(f"Imported {count} new answers from {screening_path.name}.")

    stats = get_answer_stats()
    click.echo(f"Total cached answers: {stats['total_answers']}")


@answers.command("stats")
def answers_stats():
    """Show answer cache statistics."""
    stats = get_answer_stats()
    click.echo(f"\nAnswer Cache Statistics:")
    click.echo(f"  Total answers: {stats['total_answers']}")
    click.echo(f"  Total lookups: {stats['total_lookups']}")
    click.echo(f"  Never used:    {stats['never_used']}")

    if stats["by_source"]:
        click.echo(f"\n  By Source:")
        for src, cnt in stats["by_source"].items():
            click.echo(f"    {src}: {cnt}")

    if stats["by_category"]:
        click.echo(f"\n  By Category:")
        for cat, cnt in stats["by_category"].items():
            click.echo(f"    {cat}: {cnt}")

    if stats["most_used"]:
        click.echo(f"\n  Most Used:")
        for a in stats["most_used"]:
            click.echo(f"    [{a['times_used']}x] {a['question'][:40]} -> {a['answer'][:30]}")


@cli.command()
def calibrate():
    """Show score calibration — correlate fit scores with application outcomes."""
    cal = get_score_calibration()

    if cal["total_with_outcomes"] == 0:
        click.echo("No application outcomes yet. Update job statuses first:")
        click.echo("  Track outcomes by updating application status to 'interview', 'rejected', 'offer', etc.")
        return

    click.echo("\nScore Calibration Report")
    click.echo("=" * 60)

    click.echo(f"\n  Average Fit Score by Outcome:")
    click.echo(f"  {'Status':<15}  {'Avg Score':>9}  {'Count':>5}  {'Range'}")
    click.echo(f"  {'─' * 55}")
    for status, data in cal["avg_by_status"].items():
        click.echo(
            f"  {status:<15}  {data['avg_score']:>9.1f}  {data['count']:>5}  "
            f"{data['min_score']}-{data['max_score']}"
        )

    if cal["recommended_threshold"] is not None:
        click.echo(f"\n  Recommended minimum fit score: {cal['recommended_threshold']}")
        click.echo("  (midpoint between avg rejected and avg interview scores)")
    else:
        click.echo("\n  Need both 'rejected' and 'interview' outcomes to calculate threshold.")

    if any(cal["penalty_analysis"].values()):
        click.echo(f"\n  Penalty Analysis:")
        for bucket, rules in cal["penalty_analysis"].items():
            if rules:
                click.echo(f"    {bucket.title()} applications:")
                for rule, count in sorted(rules.items(), key=lambda x: -x[1]):
                    click.echo(f"      {rule}: {count}x")

    click.echo(f"\n  Total applications with outcomes: {cal['total_with_outcomes']}")


@cli.command("batch-generate")
@click.option("--min-score", default=70, help="Generate docs for jobs above this score")
@click.option("--limit", default=5, help="Max jobs to generate for")
def batch_generate(min_score: int, limit: int):
    """Generate resume + cover letter for top-ranked jobs."""
    jobs = list_jobs(limit=100)
    ranked = [
        j for j in jobs
        if j.get("fit_score") and j["fit_score"] >= min_score
        and j.get("status") != "docs_generated"
    ]
    ranked.sort(key=lambda j: j["fit_score"], reverse=True)
    ranked = ranked[:limit]

    if not ranked:
        click.echo(f"No unprocessed jobs with fit score >= {min_score}.")
        return

    master_resume = load_master_resume()

    for j in ranked:
        job_data = get_job(j["id"])
        analysis_data = get_analysis(j["id"])
        if not job_data or not analysis_data:
            continue

        job = JobPosting(**job_data)
        analysis = JobAnalysis(**analysis_data)

        click.echo(f"\n[{j['id']}] {job.title} at {job.company} (score: {j['fit_score']})")
        _generate_docs(job, analysis, master_resume, j["id"])
        update_application(j["id"], status="docs_generated")

    click.echo(f"\nGenerated docs for {len(ranked)} jobs.")


def _generate_docs(
    job: JobPosting, analysis: JobAnalysis, master_resume: dict, job_id: int,
    *, redact: bool = True,
) -> None:
    """Generate resume and cover letter PDFs."""
    slug = _slugify(f"{job.company}-{job.title}")
    date_str = datetime.now(UTC).strftime("%Y%m%d")
    output_dir = OUTPUT_DIR / f"{slug}_{date_str}_{job_id}"

    resume_content = generate_resume_content(job, analysis, master_resume, redact=redact)
    resume_pdf = render_resume(resume_content, master_resume, output_dir)
    click.echo(f"  → Resume: {resume_pdf}")
    logger.info("Resume generated: %s", resume_pdf)

    update_application(job_id, resume_path=str(resume_pdf))

    cover_letter_content = generate_cover_letter_content(job, analysis, master_resume, redact=redact)
    cover_letter_pdf = render_cover_letter(
        cover_letter_content, master_resume, output_dir
    )
    click.echo(f"  → Cover letter: {cover_letter_pdf}")
    logger.info("Cover letter generated: %s", cover_letter_pdf)

    update_application(job_id, cover_letter_path=str(cover_letter_pdf))


@cli.command()
@click.argument("job_id", type=int)
@click.option("--headless", is_flag=True, help="Run browser without visible window")
def apply(job_id: int, headless: bool):
    """Fill out and submit a job application using browser automation."""
    import asyncio

    from src.agent.computer_use import fill_application
    from src.db.database import get_application

    init_db()

    job_data = get_job(job_id)
    if not job_data:
        click.echo(f"Job {job_id} not found.")
        return

    app_data = get_application(job_id)
    if not app_data or not app_data.get("resume_path"):
        click.echo(f"No documents for job {job_id}. Run 'generate {job_id}' first.")
        return

    application_url = job_data.get("application_url") or job_data.get("url", "")
    if not application_url:
        click.echo(f"No application URL for job {job_id}.")
        return

    master_resume = load_master_resume()

    click.echo(f"Opening application for: {job_data['title']} at {job_data['company']}")
    click.echo(f"URL: {application_url}")
    logger.info("Starting application for job ID %d at %s", job_id, application_url)

    result = asyncio.run(
        fill_application(
            application_url=application_url,
            master_resume=master_resume,
            resume_path=app_data["resume_path"],
            cover_letter_path=app_data.get("cover_letter_path", ""),
            job_id=job_id,
            headless=headless,
        )
    )

    click.echo(f"\nResult: {result['status']}")
    click.echo(f"Steps taken: {result.get('steps_taken', 0)}")
    if result.get("final_screenshot"):
        click.echo(f"Screenshot: {result['final_screenshot']}")
    if result["status"] == "submitted":
        update_application(job_id, status="applied")
        click.echo("Application submitted successfully!")
        logger.info("Application submitted for job ID: %d", job_id)


if __name__ == "__main__":
    cli()
