# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated job application pipeline: scrape job listings (Firecrawl), analyze fit (Claude API), generate tailored resumes and cover letters (LaTeX PDFs), and optionally auto-fill applications (Playwright + Claude Computer Use). Notifications and human-in-the-loop approval via Telegram bot.

## Commands

```bash
# Install
pip install -e ".[dev]"

# CLI (installed as `jaa`)
jaa scrape <url>              # Full pipeline: scrape → analyze → generate docs
jaa search <query>            # Web search for jobs
jaa discover                  # Run all configured searches/crawls from data/search_config.json
jaa list                      # List scraped jobs
jaa rank                      # Rank jobs by fit score
jaa analyze <job_id>          # Re-analyze a stored job
jaa generate <job_id>         # Re-generate resume + cover letter
jaa batch-generate            # Generate docs for top-ranked jobs
jaa apply <job_id>            # Browser automation to fill application forms
jaa skills top|roles|trends|gaps
jaa answers list|search|add|delete|import|stats
jaa calibrate                 # Score calibration report

# Lint
ruff check src/ tests/

# Tests
pytest -v --tb=short          # All tests
pytest tests/test_scraper.py  # Single file
pytest -k "test_name"         # Single test by name

# Type check
mypy src/
```

## Architecture

**Dual-mode design**: Same tool modules power both autonomous (Claude API + Agent SDK) and interactive (Claude Code CLI) modes.

```
src/
├── main.py              # Click CLI entry point (registered as `jaa`)
├── models.py            # Pydantic models: JobPosting, JobAnalysis, ResumeContent, CoverLetterContent, ScorePenalty
├── scraper/
│   ├── firecrawl_client.py   # Firecrawl scraping + Claude extraction fallback
│   └── job_discovery.py      # Search, crawl, discover_all from config
├── analyzer/
│   └── job_analyzer.py       # Claude-powered fit scoring with penalty system (base_score + adjustments)
├── generator/
│   ├── resume_generator.py   # Claude generates content → LaTeX → pdflatex → PDF
│   └── cover_letter_generator.py
├── templates/
│   ├── resume.tex            # LaTeX templates (content injected at render time)
│   └── cover_letter.tex
├── privacy/
│   └── pii_guard.py          # Token-based PII redaction ([CANDIDATE_NAME], etc.) — redact before LLM, restore after
├── db/
│   └── database.py           # SQLite: jobs, analyses, applications, job_skills, answers tables
├── agent/
│   ├── agent.py              # Claude Agent SDK autonomous loop with 9 tools
│   ├── computer_use.py       # Playwright browser automation driven by Claude screenshots
│   └── telegram_bot.py       # Notifications + /start /jobs /top /skills /calibrate commands
└── utils.py
```

**Key data files:**
- `data/master_resume.json` — source of truth for all resume/cover letter generation and skill gap analysis
- `data/search_config.json` — search queries and career page URLs for `jaa discover`
- `data/screening_answers.json` — cached answers for application form filling

## Key Patterns

- **PII redaction**: `PIIGuard` wraps all LLM calls in analyzer and generators. Redacts before sending to API, restores tokens in response. Computer Use is intentionally NOT redacted (needs real data for forms). Use `--no-redact` flag for debugging.
- **Scoring**: Two-stage system — Claude produces `base_score`, then penalty rules adjust to `fit_score`. Penalties stored per-analysis for calibration.
- **PDF generation**: Claude returns structured Pydantic models → content injected into LaTeX templates → compiled with `pdflatex`. Requires MacTeX installed.
- **Answer cache**: SQLite-backed with SHA-256 hash for exact lookup + SequenceMatcher fuzzy fallback (0.75 threshold).
- **Skill analytics**: Extracted from existing analysis data (no extra LLM calls) into `job_skills` table on every `save_analysis()`.

## Environment

Requires `.env` with: `FIRECRAWL_API_KEY`, `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_USER_ID`. See `.env.example`.

## Testing

Tests use `tmp_db` fixture (patches `DB_PATH` to a temp SQLite file) and mock all external API calls. CI runs on Python 3.11 with fake API keys — no real credentials needed for tests.

## Ruff Config

Line length 100, target Python 3.11. Notable ignores: S608 (SQL injection — column whitelisting used), S603 (subprocess — paths validated), E501 (handled by formatter). Tests allow `assert` (S101 ignored).
