"""Batch processing for Claude API calls using Anthropic Batch API.

Provides 50% cost savings on analysis calls by batching multiple jobs
into a single batch request instead of sequential synchronous calls.
"""

import json
import logging
import time
from pathlib import Path

import anthropic

from src.analyzer.job_analyzer import (
    ANALYSIS_SYSTEM_PROMPT,
    _build_preferences_text,
    _format_job_text,
    load_master_resume,
)
from src.config import get as cfg
from src.models import JobPosting
from src.privacy import PIIGuard

logger = logging.getLogger(__name__)

MASTER_RESUME_PATH = Path(__file__).parent.parent / "data" / "master_resume.json"
SCREENING_PATH = Path(__file__).parent.parent / "data" / "screening_answers.json"


def batch_analyze_jobs(
    jobs: list[tuple[int, JobPosting]], *, redact: bool = True
) -> str:
    """Submit a batch of job analyses. Returns the batch ID for polling.

    Args:
        jobs: List of (job_id, JobPosting) tuples
        redact: Whether to redact PII

    Returns:
        Batch ID string for checking results later
    """
    client = anthropic.Anthropic()
    resume = load_master_resume()

    guard = None
    if redact:
        guard = PIIGuard.from_files(MASTER_RESUME_PATH, SCREENING_PATH)
        resume = guard.redact_dict(resume)

    resume_json = json.dumps(resume, separators=(",", ":"))
    preferences_text = _build_preferences_text(resume)

    # Static content block (same for every request in the batch)
    candidate_text = (
        f"## Candidate Profile\n{resume_json}"
        f"\n\n## Candidate Preferences\n{preferences_text}"
    )

    # Get model from config (batch is Anthropic-only)
    providers = cfg("llm", "providers") or {}
    batch_model = (providers.get("anthropic") or {}).get(
        "analysis_model", "claude-sonnet-4-20250514"
    )

    requests = []
    for job_id, job in jobs:
        job_text = _format_job_text(job)
        requests.append(
            {
                "custom_id": f"analyze-{job_id}",
                "params": {
                    "model": batch_model,
                    "max_tokens": 2000,
                    "system": [
                        {
                            "type": "text",
                            "text": ANALYSIS_SYSTEM_PROMPT,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": candidate_text,
                                    "cache_control": {"type": "ephemeral"},
                                },
                                {"type": "text", "text": job_text},
                            ],
                        }
                    ],
                },
            }
        )

    batch = client.messages.batches.create(requests=requests)
    logger.info("Created batch %s with %d requests", batch.id, len(requests))
    return batch.id


def get_batch_status(batch_id: str) -> dict:
    """Get the current status of a batch job.

    Returns dict with processing_status and request counts.
    """
    client = anthropic.Anthropic()
    batch = client.messages.batches.retrieve(batch_id)
    return {
        "id": batch.id,
        "processing_status": batch.processing_status,
        "request_counts": {
            "processing": batch.request_counts.processing,
            "succeeded": batch.request_counts.succeeded,
            "errored": batch.request_counts.errored,
            "canceled": batch.request_counts.canceled,
            "expired": batch.request_counts.expired,
        },
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "ended_at": batch.ended_at.isoformat() if batch.ended_at else None,
    }


def poll_batch(batch_id: str, poll_interval: int = 30, timeout: int = 3600) -> dict:
    """Poll a batch until complete. Returns mapping of job_id -> analysis dict.

    Args:
        batch_id: The batch ID to poll
        poll_interval: Seconds between status checks
        timeout: Maximum seconds to wait before giving up

    Returns:
        Dict mapping job_id (int) -> analysis data (dict) or None for failures
    """
    client = anthropic.Anthropic()
    elapsed = 0

    while elapsed < timeout:
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status == "ended":
            break
        logger.info(
            "Batch %s: %d processing, %d succeeded, %d errored",
            batch_id,
            batch.request_counts.processing,
            batch.request_counts.succeeded,
            batch.request_counts.errored,
        )
        time.sleep(poll_interval)
        elapsed += poll_interval
    else:
        logger.warning("Batch %s timed out after %d seconds", batch_id, timeout)
        return {}

    # Retrieve results
    results = {}
    for result in client.messages.batches.results(batch_id):
        custom_id = result.custom_id  # "analyze-{job_id}"
        job_id = int(custom_id.split("-", 1)[1])

        if result.result.type == "succeeded":
            text = result.result.message.content[0].text
            try:
                results[job_id] = json.loads(text)
            except json.JSONDecodeError:
                logger.warning("Failed to parse batch result for job %d", job_id)
                results[job_id] = None
        else:
            logger.warning(
                "Batch request for job %d failed: %s", job_id, result.result.type
            )
            results[job_id] = None

    return results
