"""Analyze job postings against the user's profile using Claude."""

import json
import logging
from pathlib import Path

from anthropic import APIError, APITimeoutError, RateLimitError

from src.llm import get_router, parse_json_response
from src.models import JobAnalysis, JobPosting
from src.privacy import PIIGuard
from src.utils import retry

logger = logging.getLogger(__name__)

MASTER_RESUME_PATH = Path(__file__).parent.parent.parent / "data" / "master_resume.json"
SCREENING_PATH = Path(__file__).parent.parent.parent / "data" / "screening_answers.json"

ANALYSIS_SYSTEM_PROMPT = """\
You are an expert career advisor and resume strategist.

Analyze the provided job posting against the candidate's profile. Be honest and specific.

Use a penalty-based scoring system:

### Scoring Rules
1. Start with a base_score (0-100) reflecting how well the candidate's skills and experience match the job requirements. 90+ means near-perfect match.
2. Then apply these adjustments:
   - **Skill level mismatch**: -20 if the job requires "advanced/expert/senior" proficiency in a skill but the candidate has only beginner/elementary level
   - **Overqualification**: -10 if the job targets junior/entry-level (< 2 years) but the candidate has 5+ years of experience
   - **Missing certification**: -15 if the job explicitly requires a specific certification the candidate does not have
   - **Location mismatch**: -10 if the job is not remote AND its location is not in the candidate's preferred locations
   - **Interest alignment**: +10 if the role aligns with the candidate's target roles or stated career interests beyond just skills
   - **Role type mismatch**: -10 if the job title/function doesn't match any of the candidate's target roles
3. Calculate fit_score = base_score + sum of all adjustments (clamp to 0-100)

### Output Format
Return a JSON object with exactly these fields:

- "base_score": integer 0-100 (the raw match score before adjustments)
- "penalties": list of objects, each with:
  - "rule": string — which rule was applied (e.g., "skill_level_mismatch", "overqualification", "missing_certification", "location_mismatch", "interest_alignment", "role_type_mismatch")
  - "points": integer — the point adjustment (negative for penalties, positive for bonuses)
  - "reason": string — brief explanation of why this adjustment applies
- "fit_score": integer 0-100 (base_score + adjustments, clamped to 0-100)
- "fit_reasoning": string explaining the final score in 2-3 sentences
- "matching_skills": list of strings — skills/experience the candidate has that match requirements
- "gaps": list of strings — requirements the candidate doesn't clearly meet
- "keywords": list of strings — important terms from the job posting to emphasize in the resume
- "tailoring_strategy": string — specific advice on what to highlight, reorder, or emphasize in the resume and cover letter for this role

If no adjustments apply, return an empty penalties list. Return ONLY valid JSON, no markdown fences or extra text."""


def _build_preferences_text(resume: dict) -> str:
    """Build preferences text from resume data."""
    prefs = resume.get("preferences", {})
    pref_lines = []
    if prefs.get("target_roles"):
        pref_lines.append(f"Target roles: {', '.join(prefs['target_roles'])}")
    if prefs.get("locations"):
        pref_lines.append(f"Preferred locations: {', '.join(prefs['locations'])}")
    if prefs.get("work_modes"):
        pref_lines.append(f"Work modes: {', '.join(prefs['work_modes'])}")
    if prefs.get("job_types"):
        pref_lines.append(f"Job types: {', '.join(prefs['job_types'])}")
    if prefs.get("min_salary"):
        pref_lines.append(f"Minimum salary: {prefs['min_salary']}")
    return "\n".join(pref_lines) if pref_lines else "No preferences specified"


def _format_job_text(job: JobPosting) -> str:
    """Format job posting details for Claude prompts."""
    requirements = "\n".join(f"- {r}" for r in job.requirements) or "Not listed"
    responsibilities = "\n".join(f"- {r}" for r in job.responsibilities) or "Not listed"
    return (
        f"## Job Posting\n"
        f"Title: {job.title}\n"
        f"Company: {job.company}\n"
        f"Location: {job.location or 'Not specified'}\n"
        f"Type: {job.job_type or 'Not specified'}\n"
        f"Experience Level: {job.experience_level or 'Not specified'}\n\n"
        f"### Description\n{job.description}\n\n"
        f"### Requirements\n{requirements}\n\n"
        f"### Responsibilities\n{responsibilities}"
    )


def load_master_resume() -> dict:
    if not MASTER_RESUME_PATH.exists():
        logger.error("Master resume not found at %s", MASTER_RESUME_PATH)
        raise FileNotFoundError(
            f"Master resume not found at {MASTER_RESUME_PATH}. "
            "Create data/master_resume.json with your complete profile."
        )
    logger.debug("Loaded master resume from %s", MASTER_RESUME_PATH)
    return json.loads(MASTER_RESUME_PATH.read_text())


@retry(max_retries=3, base_delay=1.0, max_delay=30.0, exceptions=(APIError, APITimeoutError, RateLimitError, ValueError, json.JSONDecodeError))
def analyze_job(job: JobPosting, *, redact: bool = True) -> JobAnalysis:
    """Analyze a job posting against the user's master resume.

    Args:
        job: The job posting to analyze.
        redact: If True, redact PII before sending to Claude. Default True.
    """
    logger.info("Analyzing job: %s at %s", job.title, job.company)
    resume = load_master_resume()

    guard = None
    if redact:
        guard = PIIGuard.from_files(MASTER_RESUME_PATH, SCREENING_PATH)
        resume = guard.redact_dict(resume)
        logger.info("PII redacted: %d fields protected", guard.field_count)

    # Extract candidate preferences for scoring rules
    preferences_text = _build_preferences_text(resume)

    # Build content blocks
    cached_content = (
        f"## Candidate Profile\n{json.dumps(resume, separators=(',', ':'))}"
        f"\n\n## Candidate Preferences\n{preferences_text}"
    )
    variable_content = _format_job_text(job)

    router = get_router()
    response = router.generate_with_cache(
        task="analysis",
        system=ANALYSIS_SYSTEM_PROMPT,
        cached_content=cached_content,
        variable_content=variable_content,
        max_tokens=2000,
    )

    response_text = response.text
    if guard:
        response_text = guard.restore(response_text)

    analysis_data = parse_json_response(response_text)
    logger.info("Analysis complete for %s at %s: fit_score=%d (provider=%s)",
                job.title, job.company, analysis_data["fit_score"], response.provider)
    return JobAnalysis(**analysis_data)
