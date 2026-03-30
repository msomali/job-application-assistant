# Job Application Assistant

An automated job application pipeline that scrapes job listings, analyzes fit against your resume, generates tailored resumes and cover letters as PDFs, and optionally auto-fills application forms using browser automation. Notifications and human-in-the-loop approval happen through a Telegram bot.

## How It Works

1. **Discover** — Firecrawl scrapes job listings from configured search queries and career pages
2. **Analyze** — Claude evaluates each job against your master resume and produces a fit score (0-100) with penalty breakdowns
3. **Generate** — Claude writes tailored resume and cover letter content, injected into LaTeX templates and compiled to PDF
4. **Apply** — Playwright + Claude Computer Use fills out application forms in a real browser, with Telegram approval before submission

PII is automatically redacted before sending data to the LLM and restored in the output.

## Prerequisites

- Python 3.11+
- [MacTeX](https://www.tug.org/mactex/) (for `pdflatex` — PDF generation)
- [Playwright](https://playwright.dev/) browsers (for application form filling)

## Setup

```bash
# Clone the repository
git clone <repo-url>
cd job-application-assistant

# Install the package and dev dependencies
pip install -e ".[dev]"

# Install Playwright browsers (needed for auto-apply)
playwright install chromium

# Create your .env file
cp .env.example .env
# Edit .env with your API keys (see below)
```

### Environment Variables

Create a `.env` file in the project root with:

| Variable | Description | How to get it |
|---|---|---|
| `FIRECRAWL_API_KEY` | Firecrawl API key for web scraping | [firecrawl.dev](https://firecrawl.dev) |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude | [console.anthropic.com](https://console.anthropic.com) |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for notifications | Message [@BotFather](https://t.me/BotFather) on Telegram |
| `TELEGRAM_USER_ID` | Your numeric Telegram user ID | Message [@userinfobot](https://t.me/userinfobot) on Telegram |

### Data Files

These files live in `data/` and are gitignored (they contain personal information):

- **`master_resume.json`** — Your complete resume data. This is the source of truth for all resume/cover letter generation and skill gap analysis.
- **`search_config.json`** — Search queries and career page URLs used by `job discover`.
- **`screening_answers.json`** — Pre-filled answers for common application form questions (importable into the answer cache).

## CLI Commands

The CLI is installed as `job`.

### Full Pipeline

```bash
# Scrape a job URL → analyze fit → generate resume + cover letter
job scrape <url>

# Same but with PII redaction disabled (for debugging)
job scrape <url> --no-redact
```

### Job Discovery

```bash
# Search the web for jobs
job search "data engineer remote" --limit 5 --analyze-all

# Crawl a company career page
job crawl https://company.com/careers --limit 20 --include "/jobs/" --analyze-all

# Run all configured searches and crawls from search_config.json
job discover --analyze-all

# Same but using Batch API (50% cheaper, results are async)
job discover --analyze-all --batch
job batch-status <batch_id>    # Check if batch is done
job batch-collect <batch_id>   # Save results to database
```

### Browse and Rank

```bash
# List all scraped jobs with scores
job list --limit 20

# Rank jobs by fit score (filtered by minimum)
job rank --min-score 70 --limit 10
```

### Analyze and Generate

```bash
# Re-analyze a stored job
job analyze <job_id>

# Re-generate resume + cover letter for a job
job generate <job_id>

# Batch generate docs for top-ranked jobs
job batch-generate --min-score 70 --limit 5
```

### Browser Automation

```bash
# Fill out an application form using Claude Computer Use
job apply <job_id>

# Run headless (no visible browser window)
job apply <job_id> --headless
```

### Skill Analytics

```bash
# Most in-demand skills across all discovered jobs
job skills top --limit 30

# Top skills broken down by role type
job skills roles --limit 15

# Rising vs established skills (recent vs older jobs)
job skills trends --days 30

# Skills the market wants that you don't have
job skills gaps --limit 20
```

### Answer Cache

Manages cached answers for application screening questions. Answers are matched by exact hash or fuzzy text similarity.

```bash
# List cached answers
job answers list --category personal --source manual --limit 30

# Search for a cached answer (fuzzy matching)
job answers search "What is your expected salary?"

# Add a new answer
job answers add "Are you authorized to work in the US?" "Yes" --category legal

# Delete an answer
job answers delete <answer_id>

# Import answers from screening_answers.json
job answers import

# Show cache statistics
job answers stats
```

### Score Calibration

```bash
# Correlate fit scores with application outcomes
job calibrate
```

## Telegram Bot

The Telegram bot gives you mobile access to the full pipeline with notifications and human-in-the-loop approval for applications.

### Starting the Bot

```bash
python -m src.agent.telegram_bot
```

### Bot Commands

**Discovery:**
| Command | Description |
|---|---|
| `/discover` | Run full job discovery pipeline and send digest |
| `/search <query>` | Search for jobs with a custom query |
| `/scrape <url>` | Scrape and analyze a single job URL |
| `/paste [url]` | Paste a job description directly (for LinkedIn, etc.) |

**Browse:**
| Command | Description |
|---|---|
| `/jobs` | List latest jobs with scores |
| `/top` | Show top matches (score >= 70) |
| `/job <id>` | Show full job details and analysis |
| `/status` | Application tracking summary |
| `/analytics` | Conversion rates and pipeline stats |
| `/skills` | Top in-demand skills and your gaps |
| `/calibrate` | Score calibration vs outcomes |

**Actions:**
| Command | Description |
|---|---|
| `/generate <id>` | Generate resume + cover letter (sends PDFs to chat) |
| `/apply <id>` | Fill out application form via browser automation |
| `/send <id>` | Re-send generated docs to the chat |
| `/update <id> <status>` | Update job status (`interview`, `offer`, `rejected`, etc.) |

**During applications:** Reply `submit` to confirm or `skip` to cancel when the bot asks for approval.

## Autonomous Agent

The Claude Agent SDK powers a fully autonomous mode that can discover, analyze, generate docs, and apply to jobs without manual intervention (with Telegram approval gates).

### Running the Agent

```bash
# Interactive prompt
python -m src.agent.agent

# With a specific task
python -m src.agent.agent "Find data engineer jobs in NYC and generate docs for the top 3"
```

### Daily Cron Job

A daily discovery script sends a Telegram digest of new top matches:

```bash
# Run manually
python scripts/daily_discover.py

# Or set up as a cron job (runs at 8 AM daily)
# 0 8 * * * /path/to/python scripts/daily_discover.py
```

## Development

```bash
# Run all tests
pytest -v --tb=short

# Run a single test file
pytest tests/test_scraper.py

# Run a single test by name
pytest -k "test_name"

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## Project Structure

```
src/
├── main.py                          # Click CLI (jaa)
├── models.py                        # Pydantic data models
├── scraper/                         # Firecrawl scraping + job discovery
├── analyzer/                        # Claude-powered fit scoring
├── generator/                       # Resume + cover letter generation (Claude → LaTeX → PDF)
├── templates/                       # LaTeX templates
├── privacy/                         # PII redaction (token-based)
├── db/                              # SQLite database layer
├── agent/
│   ├── agent.py                     # Claude Agent SDK autonomous loop
│   ├── computer_use.py              # Playwright browser automation
│   └── telegram_bot.py              # Telegram bot for notifications + approval
└── utils.py

data/                                # Personal data (gitignored)
output/                              # Generated PDFs (gitignored)
scripts/                             # Cron and automation scripts
tests/                               # Test suite
```
