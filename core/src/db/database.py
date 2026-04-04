"""SQLite database for storing jobs, analyses, and application tracking."""

import json
import logging
import sqlite3
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "jobs.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    logger.debug("Initializing database at %s", DB_PATH)
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            url_hash TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            salary_range TEXT,
            job_type TEXT,
            experience_level TEXT,
            description TEXT,
            requirements TEXT,  -- JSON array
            responsibilities TEXT,  -- JSON array
            benefits TEXT,  -- JSON array
            application_url TEXT,
            date_posted TEXT,
            scraped_at TEXT NOT NULL,
            raw_markdown TEXT
        );

        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES jobs(id),
            fit_score INTEGER NOT NULL,
            base_score INTEGER,
            penalties TEXT,  -- JSON array of {rule, points, reason}
            fit_reasoning TEXT,
            matching_skills TEXT,  -- JSON array
            gaps TEXT,  -- JSON array
            keywords TEXT,  -- JSON array
            tailoring_strategy TEXT,
            analyzed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES jobs(id),
            status TEXT NOT NULL DEFAULT 'discovered',
            resume_path TEXT,
            cover_letter_path TEXT,
            applied_at TEXT,
            notes TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS job_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES jobs(id),
            skill TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'keyword',  -- 'keyword', 'requirement', 'gap'
            extracted_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_job_skills_skill ON job_skills(skill);
        CREATE INDEX IF NOT EXISTS idx_job_skills_job_id ON job_skills(job_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_job_skills_unique ON job_skills(job_id, skill, source);

        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            question_hash TEXT NOT NULL,
            answer TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'manual',  -- 'manual', 'llm', 'imported'
            category TEXT,  -- 'personal', 'work_authorization', 'experience', etc.
            times_used INTEGER NOT NULL DEFAULT 0,
            last_used_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_answers_hash ON answers(question_hash);
        CREATE INDEX IF NOT EXISTS idx_answers_category ON answers(category);

        CREATE TABLE IF NOT EXISTS form_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_url TEXT NOT NULL,
            step_index INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            action_data TEXT NOT NULL,
            page_url TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_form_actions_url
            ON form_actions(job_url, step_index);

        CREATE TABLE IF NOT EXISTS application_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL REFERENCES jobs(id),
            event_type TEXT NOT NULL,       -- 'submitted', 'failed', 'flagged', 'error', 'skipped'
            outcome TEXT NOT NULL,          -- 'success', 'failure', 'unknown'
            reason TEXT,                    -- ATS message or error detail
            page_url TEXT,                  -- URL at time of event
            screenshot_path TEXT,           -- confirmation/error screenshot
            steps_taken INTEGER DEFAULT 0,
            was_replay INTEGER DEFAULT 0,   -- 1 if action replay, 0 if live
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_app_events_job_id ON application_events(job_id);
        CREATE INDEX IF NOT EXISTS idx_app_events_type ON application_events(event_type);
    """)

    # Migration: add pause state columns if missing
    cursor = conn.execute("PRAGMA table_info(applications)")
    columns = {row[1] for row in cursor.fetchall()}
    if "pause_step" not in columns:
        conn.executescript("""
            ALTER TABLE applications ADD COLUMN pause_step INTEGER;
            ALTER TABLE applications ADD COLUMN pause_messages TEXT;
            ALTER TABLE applications ADD COLUMN pause_screenshot TEXT;
        """)
        logger.info("Migrated applications table: added pause state columns")

    # Migration: add submission outcome columns if missing
    if "submission_outcome" not in columns:
        conn.executescript("""
            ALTER TABLE applications ADD COLUMN submission_outcome TEXT;
            ALTER TABLE applications ADD COLUMN failure_reason TEXT;
        """)
        logger.info("Migrated applications table: added submission_outcome, failure_reason")

    conn.commit()

    # Migrate: add base_score and penalties columns if missing (existing databases)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(analyses)").fetchall()}
    if "base_score" not in cols:
        conn.execute("ALTER TABLE analyses ADD COLUMN base_score INTEGER")
    if "penalties" not in cols:
        conn.execute("ALTER TABLE analyses ADD COLUMN penalties TEXT")
    conn.commit()

    conn.close()


def job_exists_by_url(url: str) -> int | None:
    """Return job_id if URL already exists in DB, else None."""
    conn = get_connection()
    url_hash = sha256(url.encode()).hexdigest()[:16]
    row = conn.execute("SELECT id FROM jobs WHERE url_hash = ?", (url_hash,)).fetchone()
    conn.close()
    return row["id"] if row else None


def save_job(job_data: dict, url: str, raw_markdown: str | None = None) -> int:
    logger.debug("Saving job: %s at %s (url=%s)", job_data.get("title"), job_data.get("company"), url)
    conn = get_connection()
    url_hash = sha256(url.encode()).hexdigest()[:16]
    now = datetime.now(UTC).isoformat()

    try:
        conn.execute(
            """INSERT INTO jobs (url, url_hash, title, company, location, salary_range,
               job_type, experience_level, description, requirements, responsibilities,
               benefits, application_url, date_posted, scraped_at, raw_markdown)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                url,
                url_hash,
                job_data["title"],
                job_data["company"],
                job_data.get("location"),
                job_data.get("salary_range"),
                job_data.get("job_type"),
                job_data.get("experience_level"),
                job_data.get("description"),
                json.dumps(job_data.get("requirements", [])),
                json.dumps(job_data.get("responsibilities", [])),
                json.dumps(job_data.get("benefits", [])),
                job_data.get("application_url"),
                job_data.get("date_posted"),
                now,
                raw_markdown,
            ),
        )
        conn.commit()
        job_id = conn.execute(
            "SELECT id FROM jobs WHERE url_hash = ?", (url_hash,)
        ).fetchone()["id"]
        logger.info("Saved new job with ID: %d", job_id)
    except sqlite3.IntegrityError:
        job_id = conn.execute(
            "SELECT id FROM jobs WHERE url_hash = ?", (url_hash,)
        ).fetchone()["id"]
        logger.debug("Job already exists with ID: %d (url=%s)", job_id, url)
    finally:
        conn.close()

    return job_id


def save_analysis(job_id: int, analysis: dict) -> int:
    logger.debug("Saving analysis for job ID: %d (fit_score=%d)", job_id, analysis.get("fit_score", 0))
    conn = get_connection()
    now = datetime.now(UTC).isoformat()
    # Serialize penalties list if present
    penalties_raw = analysis.get("penalties", [])
    if penalties_raw and hasattr(penalties_raw[0], "model_dump"):
        penalties_json = json.dumps([p.model_dump() for p in penalties_raw])
    else:
        penalties_json = json.dumps(penalties_raw)

    conn.execute(
        """INSERT INTO analyses (job_id, fit_score, base_score, penalties,
           fit_reasoning, matching_skills, gaps, keywords, tailoring_strategy, analyzed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job_id,
            analysis["fit_score"],
            analysis.get("base_score"),
            penalties_json,
            analysis.get("fit_reasoning"),
            json.dumps(analysis.get("matching_skills", [])),
            json.dumps(analysis.get("gaps", [])),
            json.dumps(analysis.get("keywords", [])),
            analysis.get("tailoring_strategy"),
            now,
        ),
    )
    conn.commit()
    analysis_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()

    # Auto-extract and store skills from the analysis
    save_job_skills(job_id, analysis)

    return analysis_id


_ALLOWED_APP_COLUMNS = frozenset({
    "status", "resume_path", "cover_letter_path", "applied_at", "notes", "updated_at",
    "job_id", "pause_step", "pause_messages", "pause_screenshot",
    "submission_outcome", "failure_reason",
})


def update_application(job_id: int, **fields) -> None:
    logger.debug("Updating application for job ID: %d, fields=%s", job_id, list(fields.keys()))
    # Whitelist column names to prevent SQL injection
    bad_keys = set(fields.keys()) - _ALLOWED_APP_COLUMNS
    if bad_keys:
        raise ValueError(f"Invalid application fields: {bad_keys}")

    conn = get_connection()
    now = datetime.now(UTC).isoformat()
    fields["updated_at"] = now

    existing = conn.execute(
        "SELECT id FROM applications WHERE job_id = ?", (job_id,)
    ).fetchone()

    if existing:
        sets = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(
            f"UPDATE applications SET {sets} WHERE job_id = ?",
            (*fields.values(), job_id),
        )
    else:
        fields["job_id"] = job_id
        fields.setdefault("status", "discovered")
        cols = ", ".join(fields)
        placeholders = ", ".join("?" for _ in fields)
        conn.execute(
            f"INSERT INTO applications ({cols}) VALUES ({placeholders})",
            tuple(fields.values()),
        )

    conn.commit()
    conn.close()


def get_job(job_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    job = dict(row)
    for field in ("requirements", "responsibilities", "benefits"):
        if job.get(field):
            job[field] = json.loads(job[field])
    return job


def get_analysis(job_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM analyses WHERE job_id = ? ORDER BY analyzed_at DESC LIMIT 1",
        (job_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    analysis = dict(row)
    for field in ("matching_skills", "gaps", "keywords", "penalties"):
        if analysis.get(field):
            analysis[field] = json.loads(analysis[field])
    return analysis


def get_application(job_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM applications WHERE job_id = ? ORDER BY updated_at DESC LIMIT 1",
        (job_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def log_application_event(
    job_id: int,
    event_type: str,
    outcome: str,
    reason: str | None = None,
    page_url: str | None = None,
    screenshot_path: str | None = None,
    steps_taken: int = 0,
    was_replay: bool = False,
) -> int:
    """Log an application submission event (audit trail).

    event_type: 'submitted', 'failed', 'flagged', 'error', 'skipped'
    outcome: 'success', 'failure', 'unknown'
    """
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO application_events
           (job_id, event_type, outcome, reason, page_url, screenshot_path,
            steps_taken, was_replay)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, event_type, outcome, reason, page_url, screenshot_path,
         steps_taken, 1 if was_replay else 0),
    )
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    logger.info("Logged application event: job=%d type=%s outcome=%s", job_id, event_type, outcome)
    return event_id


def get_application_events(job_id: int) -> list[dict]:
    """Get all submission events for a job, newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM application_events WHERE job_id = ? ORDER BY created_at DESC",
        (job_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_pause_state(job_id: int, step: int, messages: list, screenshot: str) -> None:
    """Save Computer Use loop state for later resumption."""
    update_application(
        job_id,
        status="paused",
        pause_step=step,
        pause_messages=json.dumps(messages),
        pause_screenshot=screenshot,
    )
    logger.info("Saved pause state for job %d at step %d", job_id, step)


def get_pause_state(job_id: int) -> dict | None:
    """Load saved pause state. Returns None if not paused."""
    conn = get_connection()
    row = conn.execute(
        "SELECT pause_step, pause_messages, pause_screenshot FROM applications "
        "WHERE job_id = ? AND status = 'paused'",
        (job_id,),
    ).fetchone()
    conn.close()
    if row is None or row["pause_step"] is None:
        return None
    return {
        "step": row["pause_step"],
        "messages": json.loads(row["pause_messages"]) if row["pause_messages"] else [],
        "screenshot": row["pause_screenshot"],
    }


def clear_pause_state(job_id: int) -> None:
    """Clear pause state after successful resume."""
    update_application(
        job_id,
        pause_step=None,
        pause_messages=None,
        pause_screenshot=None,
    )
    logger.info("Cleared pause state for job %d", job_id)


# ---------------------------------------------------------------------------
# Form action recording (replay cache for Computer Use)
# ---------------------------------------------------------------------------


def save_form_actions(job_url: str, actions: list[dict]) -> None:
    """Save a sequence of form-filling actions for a job URL.

    Each action is {action_type, action_data, page_url, step_index}.
    Clears any existing actions for this URL first.
    """
    conn = get_connection()
    conn.execute("DELETE FROM form_actions WHERE job_url = ?", (job_url,))
    now = datetime.now(UTC).isoformat()
    for i, act in enumerate(actions):
        conn.execute(
            "INSERT INTO form_actions (job_url, step_index, action_type, action_data, page_url, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (job_url, i, act["action_type"], json.dumps(act["action_data"]), act.get("page_url", ""), now),
        )
    conn.commit()
    conn.close()
    logger.info("Saved %d form actions for %s", len(actions), job_url)


def get_form_actions(job_url: str) -> list[dict]:
    """Load saved form actions for a job URL, ordered by step."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT step_index, action_type, action_data, page_url FROM form_actions "
        "WHERE job_url = ? ORDER BY step_index",
        (job_url,),
    ).fetchall()
    conn.close()
    return [
        {
            "step_index": r["step_index"],
            "action_type": r["action_type"],
            "action_data": json.loads(r["action_data"]),
            "page_url": r["page_url"],
        }
        for r in rows
    ]


def clear_form_actions(job_url: str) -> None:
    """Delete saved form actions for a URL."""
    conn = get_connection()
    conn.execute("DELETE FROM form_actions WHERE job_url = ?", (job_url,))
    conn.commit()
    conn.close()


def list_jobs(limit: int = 20) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT j.id, j.title, j.company, j.location, j.scraped_at,
           a.fit_score, app.status
           FROM jobs j
           LEFT JOIN analyses a ON a.job_id = j.id
           LEFT JOIN applications app ON app.job_id = j.id
           ORDER BY a.fit_score DESC NULLS LAST, j.scraped_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_collected_jobs(min_score: int = 0, limit: int = 20) -> list[dict]:
    """Get jobs in 'collected' status, sorted by fit score."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT j.id, j.title, j.company, j.location,
           a.fit_score, a.matching_skills, a.gaps, a.tailoring_strategy,
           app.status
           FROM jobs j
           JOIN analyses a ON a.job_id = j.id
           JOIN applications app ON app.job_id = j.id
           WHERE app.status = 'collected' AND a.fit_score >= ?
           ORDER BY a.fit_score DESC
           LIMIT ?""",
        (min_score, limit),
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        for field in ("matching_skills", "gaps"):
            if d.get(field):
                d[field] = json.loads(d[field])
        results.append(d)
    return results


def get_uncollected_jobs(min_score: int = 0, limit: int = 50) -> list[dict]:
    """Get analyzed jobs that haven't been collected yet (status = 'discovered')."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT j.id, j.title, j.company, j.location,
           a.fit_score, app.status
           FROM jobs j
           JOIN analyses a ON a.job_id = j.id
           LEFT JOIN applications app ON app.job_id = j.id
           WHERE (app.status = 'discovered' OR app.status IS NULL)
             AND a.fit_score >= ?
           ORDER BY a.fit_score DESC
           LIMIT ?""",
        (min_score, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def bulk_collect(job_ids: list[int]) -> int:
    """Mark multiple jobs as collected. Returns count updated."""
    conn = get_connection()
    now = datetime.now(UTC).isoformat()
    count = 0
    for jid in job_ids:
        existing = conn.execute(
            "SELECT id FROM applications WHERE job_id = ?", (jid,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE applications SET status = 'collected', updated_at = ? WHERE job_id = ?",
                (now, jid),
            )
        else:
            conn.execute(
                "INSERT INTO applications (job_id, status, updated_at) VALUES (?, 'collected', ?)",
                (jid, now),
            )
        count += 1
    conn.commit()
    conn.close()
    return count


def save_job_skills(job_id: int, analysis: dict) -> int:
    """Extract and store skills from an analysis result.

    Pulls skills from three sources in the analysis:
    - keywords: terms to emphasize (source='keyword')
    - matching_skills: candidate skills that match (source='requirement')
    - gaps: skills the candidate lacks (source='gap')

    Returns the number of skills saved.
    """
    conn = get_connection()
    now = datetime.now(UTC).isoformat()
    count = 0

    sources = {
        "keyword": analysis.get("keywords", []),
        "requirement": analysis.get("matching_skills", []),
        "gap": analysis.get("gaps", []),
    }

    for source, skills in sources.items():
        for raw_skill in skills:
            skill = raw_skill.strip().lower()
            if not skill:
                continue
            try:
                conn.execute(
                    """INSERT INTO job_skills (job_id, skill, source, extracted_at)
                       VALUES (?, ?, ?, ?)""",
                    (job_id, skill, source, now),
                )
                count += 1
            except sqlite3.IntegrityError:
                pass  # duplicate (job_id, skill, source)

    conn.commit()
    conn.close()
    logger.debug("Saved %d skills for job ID %d", count, job_id)
    return count


def get_skill_stats(limit: int = 30) -> list[dict]:
    """Get most in-demand skills across all discovered jobs.

    Returns skills sorted by frequency (number of distinct jobs requiring them).
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT skill, COUNT(DISTINCT job_id) as job_count,
                  GROUP_CONCAT(DISTINCT source) as sources
           FROM job_skills
           GROUP BY skill
           ORDER BY job_count DESC, skill ASC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_skill_stats_by_role(limit: int = 20) -> dict[str, list[dict]]:
    """Get top skills broken down by job title pattern.

    Groups jobs by simplified title (e.g., 'Data Engineer', 'ML Engineer')
    and returns top skills for each.
    """
    conn = get_connection()

    # Get distinct title patterns
    titles = conn.execute(
        "SELECT DISTINCT title FROM jobs"
    ).fetchall()

    # Simplify titles into role categories
    role_map: dict[str, list[int]] = {}
    for row in titles:
        title = row["title"].lower()
        if "data engineer" in title or "analytics engineer" in title:
            role = "Data/Analytics Engineer"
        elif "data scientist" in title or "machine learning" in title or "ml " in title or "ai " in title:
            role = "Data Scientist / ML Engineer"
        elif "data analyst" in title or "business intelligence" in title or "bi " in title:
            role = "Data/BI Analyst"
        elif "software" in title or "backend" in title or "fullstack" in title or "full stack" in title:
            role = "Software Engineer"
        else:
            role = "Other"

        job_ids = conn.execute(
            "SELECT id FROM jobs WHERE title = ?", (row["title"],)
        ).fetchall()
        role_map.setdefault(role, []).extend(r["id"] for r in job_ids)

    result = {}
    for role, job_ids in role_map.items():
        if not job_ids:
            continue
        placeholders = ",".join("?" for _ in job_ids)
        rows = conn.execute(
            f"""SELECT skill, COUNT(DISTINCT job_id) as job_count
                FROM job_skills
                WHERE job_id IN ({placeholders})
                GROUP BY skill
                ORDER BY job_count DESC
                LIMIT ?""",
            (*job_ids, limit),
        ).fetchall()
        result[role] = [dict(r) for r in rows]

    conn.close()
    return result


def get_skill_trend(days: int = 30) -> dict[str, list[dict]]:
    """Compare skill demand between recent jobs and older jobs.

    Returns two lists: 'rising' skills (more common recently) and
    'established' skills (consistently in demand).
    """
    conn = get_connection()

    cutoff = f"datetime('now', '-{days} days')"

    recent = conn.execute(
        f"""SELECT skill, COUNT(DISTINCT js.job_id) as job_count
            FROM job_skills js
            JOIN jobs j ON j.id = js.job_id
            WHERE j.scraped_at >= {cutoff}
            GROUP BY skill
            ORDER BY job_count DESC
            LIMIT 50"""
    ).fetchall()

    older = conn.execute(
        f"""SELECT skill, COUNT(DISTINCT js.job_id) as job_count
            FROM job_skills js
            JOIN jobs j ON j.id = js.job_id
            WHERE j.scraped_at < {cutoff}
            GROUP BY skill
            ORDER BY job_count DESC
            LIMIT 50"""
    ).fetchall()

    conn.close()

    recent_map = {r["skill"]: r["job_count"] for r in recent}
    older_map = {r["skill"]: r["job_count"] for r in older}

    rising = []
    for skill, count in recent_map.items():
        old_count = older_map.get(skill, 0)
        if count > old_count:
            rising.append({"skill": skill, "recent": count, "older": old_count})

    rising.sort(key=lambda x: x["recent"] - x["older"], reverse=True)

    established = []
    for skill, count in recent_map.items():
        old_count = older_map.get(skill, 0)
        if old_count >= count and count > 0:
            established.append({"skill": skill, "recent": count, "older": old_count})

    return {"rising": rising[:20], "established": established[:20]}


def get_skill_gaps(master_skills: list[str], limit: int = 20) -> list[dict]:
    """Compare market demand against the user's skills.

    Returns the most in-demand skills that the user does NOT have,
    sorted by how many jobs require them.
    """
    user_skills = {s.strip().lower() for s in master_skills}

    conn = get_connection()
    rows = conn.execute(
        """SELECT skill, COUNT(DISTINCT job_id) as job_count
           FROM job_skills
           GROUP BY skill
           ORDER BY job_count DESC"""
    ).fetchall()
    conn.close()

    gaps = []
    for r in rows:
        if r["skill"] not in user_skills:
            gaps.append({"skill": r["skill"], "job_count": r["job_count"]})
            if len(gaps) >= limit:
                break

    return gaps


def _normalize_question(text: str) -> str:
    """Normalize a question for consistent hashing.

    Lowercases, strips whitespace, removes trailing punctuation,
    collapses multiple spaces.
    """
    import re
    text = text.lower().strip()
    text = re.sub(r"[?.:!*]+$", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _hash_question(text: str) -> str:
    """Hash a normalized question for fast exact lookup."""
    return sha256(_normalize_question(text).encode()).hexdigest()[:32]


def save_answer(
    question: str,
    answer: str,
    source: str = "manual",
    category: str | None = None,
) -> int:
    """Save or update a cached answer.

    If a question with the same hash exists, updates the answer.
    Returns the answer ID.
    """
    conn = get_connection()
    now = datetime.now(UTC).isoformat()
    q_hash = _hash_question(question)
    normalized = _normalize_question(question)

    existing = conn.execute(
        "SELECT id FROM answers WHERE question_hash = ?", (q_hash,)
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE answers SET answer = ?, source = ?, category = ?, updated_at = ?
               WHERE question_hash = ?""",
            (answer, source, category, now, q_hash),
        )
        conn.commit()
        answer_id = existing["id"]
        logger.debug("Updated answer ID %d for question: %s", answer_id, normalized[:50])
    else:
        conn.execute(
            """INSERT INTO answers (question, question_hash, answer, source, category,
                   times_used, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 0, ?, ?)""",
            (normalized, q_hash, answer, source, category, now, now),
        )
        conn.commit()
        answer_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        logger.debug("Saved new answer ID %d for question: %s", answer_id, normalized[:50])

    conn.close()
    return answer_id


def find_answer(question: str) -> dict | None:
    """Look up a cached answer by exact match (after normalization).

    Returns the answer dict if found, or None.
    """
    conn = get_connection()
    q_hash = _hash_question(question)

    row = conn.execute(
        "SELECT * FROM answers WHERE question_hash = ?", (q_hash,)
    ).fetchone()

    if row:
        # Update usage stats
        now = datetime.now(UTC).isoformat()
        conn.execute(
            "UPDATE answers SET times_used = times_used + 1, last_used_at = ? WHERE id = ?",
            (now, row["id"]),
        )
        conn.commit()

    conn.close()
    return dict(row) if row else None


def find_answer_fuzzy(question: str, threshold: float | None = None) -> dict | None:
    """Look up a cached answer using fuzzy matching.

    First tries exact match. If no match, scans all answers and returns
    the best fuzzy match above the similarity threshold.

    Uses SequenceMatcher for similarity (no external dependency).
    """
    if threshold is None:
        from src.config import get as cfg
        threshold = cfg("matching", "fuzzy_threshold", 0.75)

    # Try exact first
    exact = find_answer(question)
    if exact:
        return exact

    from difflib import SequenceMatcher

    normalized = _normalize_question(question)
    conn = get_connection()
    rows = conn.execute("SELECT * FROM answers").fetchall()
    conn.close()

    best_match = None
    best_ratio = 0.0

    for row in rows:
        ratio = SequenceMatcher(None, normalized, row["question"]).ratio()
        if ratio > best_ratio and ratio >= threshold:
            best_ratio = ratio
            best_match = row

    if best_match:
        # Update usage stats for the fuzzy match
        conn = get_connection()
        now = datetime.now(UTC).isoformat()
        conn.execute(
            "UPDATE answers SET times_used = times_used + 1, last_used_at = ? WHERE id = ?",
            (now, best_match["id"]),
        )
        conn.commit()
        conn.close()
        result = dict(best_match)
        result["_fuzzy_score"] = best_ratio
        return result

    return None


def list_answers(
    category: str | None = None,
    source: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List cached answers, optionally filtered by category or source."""
    conn = get_connection()
    query = "SELECT * FROM answers WHERE 1=1"
    params: list = []

    if category:
        query += " AND category = ?"
        params.append(category)
    if source:
        query += " AND source = ?"
        params.append(source)

    query += " ORDER BY times_used DESC, updated_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_answer(answer_id: int) -> bool:
    """Delete a cached answer by ID. Returns True if deleted."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM answers WHERE id = ?", (answer_id,))
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def get_answer_stats() -> dict:
    """Get answer cache statistics."""
    conn = get_connection()

    total = conn.execute("SELECT COUNT(*) FROM answers").fetchone()[0]
    by_source = {}
    rows = conn.execute(
        "SELECT source, COUNT(*) as cnt FROM answers GROUP BY source"
    ).fetchall()
    for r in rows:
        by_source[r["source"]] = r["cnt"]

    by_category = {}
    rows = conn.execute(
        "SELECT category, COUNT(*) as cnt FROM answers GROUP BY category"
    ).fetchall()
    for r in rows:
        by_category[r["category"] or "uncategorized"] = r["cnt"]

    total_uses = conn.execute(
        "SELECT COALESCE(SUM(times_used), 0) FROM answers"
    ).fetchone()[0]

    most_used = conn.execute(
        "SELECT question, answer, times_used FROM answers ORDER BY times_used DESC LIMIT 5"
    ).fetchall()

    never_used = conn.execute(
        "SELECT COUNT(*) FROM answers WHERE times_used = 0"
    ).fetchone()[0]

    conn.close()

    return {
        "total_answers": total,
        "by_source": by_source,
        "by_category": by_category,
        "total_lookups": total_uses,
        "never_used": never_used,
        "most_used": [dict(r) for r in most_used],
    }


def import_screening_answers(screening_path: str | Path) -> int:
    """Import answers from screening_answers.json into the answer cache.

    Flattens the nested JSON structure into individual Q&A pairs.
    Existing answers (by question hash) are NOT overwritten.
    Returns the number of new answers imported.
    """
    screening_path = Path(screening_path)
    if not screening_path.exists():
        logger.warning("Screening answers file not found: %s", screening_path)
        return 0

    data = json.loads(screening_path.read_text())
    count = 0

    # Map of sections to category names
    section_map = {
        "personal": "personal",
        "work_authorization": "work_authorization",
        "experience": "experience",
        "education": "education",
        "job_preferences": "job_preferences",
        "diversity": "diversity",
        "common_questions": "common_questions",
    }

    for section_key, category in section_map.items():
        section = data.get(section_key, {})
        if not isinstance(section, dict):
            continue

        for field_key, value in section.items():
            if field_key.startswith("_"):
                continue

            # Convert the field key to a natural question
            question = field_key.replace("_", " ")
            # Convert value to string
            if isinstance(value, bool):
                answer = "Yes" if value else "No"
            elif isinstance(value, (list, dict)):
                answer = json.dumps(value)
            elif value is None or str(value).strip() == "":
                continue
            else:
                answer = str(value)

            # Check if already exists
            q_hash = _hash_question(question)
            conn = get_connection()
            existing = conn.execute(
                "SELECT id FROM answers WHERE question_hash = ?", (q_hash,)
            ).fetchone()
            conn.close()

            if not existing:
                save_answer(question, answer, source="imported", category=category)
                count += 1

    logger.info("Imported %d answers from screening_answers.json", count)
    return count


def get_score_calibration() -> dict:
    """Correlate fit scores with application outcomes for calibration.

    Returns avg fit score per outcome status, recommended threshold,
    and penalty frequency analysis to identify which rules help most.
    """
    conn = get_connection()

    # Average fit score by outcome
    avg_by_status = {}
    rows = conn.execute(
        """SELECT app.status, AVG(a.fit_score) as avg_score,
                  COUNT(*) as count, MIN(a.fit_score) as min_score,
                  MAX(a.fit_score) as max_score
           FROM applications app
           JOIN analyses a ON a.job_id = app.job_id
           WHERE app.status IN ('applied', 'interview', 'offer', 'rejected', 'no_response')
           GROUP BY app.status"""
    ).fetchall()
    for r in rows:
        avg_by_status[r["status"]] = {
            "avg_score": round(r["avg_score"], 1),
            "count": r["count"],
            "min_score": r["min_score"],
            "max_score": r["max_score"],
        }

    # Recommended threshold: midpoint between avg rejected and avg interview scores
    rejected_avg = avg_by_status.get("rejected", {}).get("avg_score")
    interview_avg = avg_by_status.get("interview", {}).get("avg_score")
    if rejected_avg and interview_avg:
        recommended_threshold = round((rejected_avg + interview_avg) / 2)
    else:
        recommended_threshold = None

    # Penalty frequency: which penalties appear most in rejected vs successful apps
    penalty_analysis = {"successful": {}, "rejected": {}}
    rows = conn.execute(
        """SELECT app.status, a.penalties
           FROM applications app
           JOIN analyses a ON a.job_id = app.job_id
           WHERE app.status IN ('interview', 'offer', 'rejected')
             AND a.penalties IS NOT NULL"""
    ).fetchall()
    for r in rows:
        penalties = json.loads(r["penalties"]) if r["penalties"] else []
        bucket = "rejected" if r["status"] == "rejected" else "successful"
        for p in penalties:
            rule = p.get("rule", "unknown")
            penalty_analysis[bucket][rule] = penalty_analysis[bucket].get(rule, 0) + 1

    conn.close()

    return {
        "avg_by_status": avg_by_status,
        "recommended_threshold": recommended_threshold,
        "penalty_analysis": penalty_analysis,
        "total_with_outcomes": sum(v["count"] for v in avg_by_status.values()),
    }


def get_analytics() -> dict:
    """Get application analytics and conversion rates."""
    conn = get_connection()

    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    analyzed = conn.execute(
        "SELECT COUNT(DISTINCT job_id) FROM analyses"
    ).fetchone()[0]

    status_counts = {}
    rows = conn.execute(
        "SELECT status, COUNT(*) as cnt FROM applications GROUP BY status"
    ).fetchall()
    for r in rows:
        status_counts[r["status"]] = r["cnt"]

    # Conversion rates
    collected = status_counts.get("collected", 0)
    docs_gen = status_counts.get("docs_generated", 0)
    applied = status_counts.get("applied", 0)
    interview = status_counts.get("interview", 0)
    offer = status_counts.get("offer", 0)
    rejected = status_counts.get("rejected", 0)

    # Average fit score by status
    avg_scores = {}
    rows = conn.execute(
        """SELECT app.status, AVG(a.fit_score) as avg_score
           FROM applications app
           JOIN analyses a ON a.job_id = app.job_id
           GROUP BY app.status"""
    ).fetchall()
    for r in rows:
        avg_scores[r["status"]] = round(r["avg_score"], 1)

    # Jobs discovered in last 7 days
    recent = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE scraped_at >= datetime('now', '-7 days')"
    ).fetchone()[0]

    conn.close()

    return {
        "total_discovered": total,
        "analyzed": analyzed,
        "collected": collected,
        "docs_generated": docs_gen,
        "applied": applied,
        "interview": interview,
        "offer": offer,
        "rejected": rejected,
        "recent_7d": recent,
        "avg_scores_by_status": avg_scores,
        "conversion": {
            "discover_to_collected": f"{collected}/{total}" if total else "0/0",
            "collected_to_docs": f"{docs_gen}/{collected}" if collected else "0/0",
            "docs_to_applied": f"{applied}/{docs_gen}" if docs_gen else "0/0",
            "applied_to_interview": f"{interview}/{applied}" if applied else "0/0",
            "interview_to_offer": f"{offer}/{interview}" if interview else "0/0",
        },
    }
