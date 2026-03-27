"""Analyze job postings against the user's profile using Claude."""

import json
import logging
from pathlib import Path

import anthropic
from anthropic import APIError, APITimeoutError, RateLimitError

from src.models import JobAnalysis, JobPosting
from src.privacy import PIIGuard
from src.utils import retry

logger = logging.getLogger(__name__)

MASTER_RESUME_PATH = Path(__file__).parent.parent.parent / "data" / "master_resume.json"
SCREENING_PATH = Path(__file__).parent.parent.parent / "data" / "screening_answers.json"

ANALYSIS_PROMPT = """\
You are an expert career advisor and resume strategist.

Analyze the following job posting against the candidate's profile. Be honest and specific.

## Job Posting
Title: {title}
Company: {company}
Location: {location}
Type: {job_type}
Experience Level: {experience_level}

### Description
{description}

### Requirements
{requirements}

### Responsibilities
{responsibilities}

## Candidate Profile
{resume}

## Candidate Preferences
{preferences}

## Your Task
Analyze how well this candidate fits the role using a penalty-based scoring system.

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

If no adjustments apply, return an empty penalties list. Return ONLY valid JSON, no markdown fences or extra text.
"""


def load_master_resume() -> dict:
    if not MASTER_RESUME_PATH.exists():
        logger.error("Master resume not found at %s", MASTER_RESUME_PATH)
        raise FileNotFoundError(
            f"Master resume not found at {MASTER_RESUME_PATH}. "
            "Create data/master_resume.json with your complete profile."
        )
    logger.debug("Loaded master resume from %s", MASTER_RESUME_PATH)
    return json.loads(MASTER_RESUME_PATH.read_text())


@retry(max_retries=3, base_delay=1.0, max_delay=30.0, exceptions=(APIError, APITimeoutError, RateLimitError))
def analyze_job(job: JobPosting, *, redact: bool = True) -> JobAnalysis:
    """Analyze a job posting against the user's master resume.

    Args:
        job: The job posting to analyze.
        redact: If True, redact PII before sending to Claude. Default True.
    """
    logger.info("Analyzing job: %s at %s", job.title, job.company)
    resume = load_master_resume()
    client = anthropic.Anthropic()

    guard = None
    if redact:
        guard = PIIGuard.from_files(MASTER_RESUME_PATH, SCREENING_PATH)
        resume = guard.redact_dict(resume)
        logger.info("PII redacted: %d fields protected", guard.field_count)

    # Extract candidate preferences for scoring rules
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
    preferences_text = "\n".join(pref_lines) if pref_lines else "No preferences specified"

    prompt = ANALYSIS_PROMPT.format(
        title=job.title,
        company=job.company,
        location=job.location or "Not specified",
        job_type=job.job_type or "Not specified",
        experience_level=job.experience_level or "Not specified",
        description=job.description,
        requirements="\n".join(f"- {r}" for r in job.requirements) or "Not listed",
        responsibilities="\n".join(f"- {r}" for r in job.responsibilities)
        or "Not listed",
        resume=json.dumps(resume, indent=2),
        preferences=preferences_text,
    )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text
    if guard:
        response_text = guard.restore(response_text)

    analysis_data = json.loads(response_text)
    logger.info("Analysis complete for %s at %s: fit_score=%d", job.title, job.company, analysis_data["fit_score"])
    return JobAnalysis(**analysis_data)
