"""PII Guard — token-based redaction and restoration for LLM calls.

Replaces personally identifiable information with deterministic tokens
before sending to LLM APIs, then restores real values in responses.

    guard = PIIGuard.from_files("data/master_resume.json", "data/screening_answers.json")
    redacted = guard.redact(text_with_pii)
    # ... send redacted text to LLM, get response ...
    restored = guard.restore(llm_response)
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# PII fields mapped to their token names and extraction paths.
# Format: (token_name, source_file, json_path)
# json_path uses dot notation: "personal.email" means data["personal"]["email"]
_PII_FIELDS = [
    # From master_resume.json
    ("CANDIDATE_NAME", "resume", "name"),
    ("CANDIDATE_CONTACT", "resume", "contact"),
    # From screening_answers.json
    ("CANDIDATE_FIRST_NAME", "screening", "personal.first_name"),
    ("CANDIDATE_LAST_NAME", "screening", "personal.last_name"),
    ("CANDIDATE_EMAIL", "screening", "personal.email"),
    ("CANDIDATE_PHONE", "screening", "personal.phone"),
    ("CANDIDATE_LINKEDIN", "screening", "personal.linkedin"),
    ("CANDIDATE_GITHUB", "screening", "personal.github"),
    ("CANDIDATE_ZIP", "screening", "personal.zip_code"),
    ("CANDIDATE_PREFERRED_NAME", "screening", "personal.preferred_name"),
    ("CANDIDATE_WEBSITE", "screening", "personal.website"),
]

# Reference PII — people mentioned in the resume (supervisors, recommenders)
# These are extracted dynamically from resume references and recommendations.
_REFERENCE_TOKEN_PREFIX = "REFERENCE"
_RECOMMENDER_TOKEN_PREFIX = "RECOMMENDER"

# Fields that should NOT be redacted (needed for LLM quality):
# - City/State (location matching)
# - Country (work authorization context)
# - Degree names, institution names (education matching)
# - Job titles, company names in experience (career trajectory)


def _get_nested(data: dict, path: str) -> str | None:
    """Get a value from a nested dict using dot notation."""
    keys = path.split(".")
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    if isinstance(current, str) and current.strip():
        return current.strip()
    return None


class PIIGuard:
    """Token-based PII redaction and restoration.

    Replaces real PII values with bracketed tokens like [CANDIDATE_NAME]
    before LLM calls, and restores them in LLM responses.

    Token-based approach advantages over dummy-name approach:
    - Deterministic: tokens are always the same, no gender/persona logic
    - Unambiguous: LLM can't hallucinate around tokens
    - Reliable restore: simple string replace, not fragile regex
    - Self-documenting: tokens describe what they replace
    """

    def __init__(self, pii_map: dict[str, str]):
        """Initialize with a mapping of token_name -> real_value.

        Args:
            pii_map: e.g. {"CANDIDATE_NAME": "John Doe", "CANDIDATE_EMAIL": "john@example.com"}
        """
        # Filter out empty values and sort by value length descending
        # so longer matches are replaced first (e.g., full name before first name)
        self._pii_map: dict[str, str] = {
            k: v for k, v in pii_map.items() if v and v.strip()
        }
        self._sorted_tokens = sorted(
            self._pii_map.items(), key=lambda kv: len(kv[1]), reverse=True
        )
        self._redaction_count = 0

    @classmethod
    def from_files(
        cls,
        resume_path: str | Path,
        screening_path: str | Path | None = None,
    ) -> "PIIGuard":
        """Create a PIIGuard from master_resume.json and screening_answers.json.

        Args:
            resume_path: Path to master_resume.json
            screening_path: Path to screening_answers.json (optional)
        """
        resume_path = Path(resume_path)
        resume_data = json.loads(resume_path.read_text()) if resume_path.exists() else {}

        screening_data = {}
        if screening_path:
            screening_path = Path(screening_path)
            if screening_path.exists():
                screening_data = json.loads(screening_path.read_text())

        pii_map: dict[str, str] = {}

        # Extract defined PII fields
        for token_name, source, json_path in _PII_FIELDS:
            data = resume_data if source == "resume" else screening_data
            value = _get_nested(data, json_path)
            if value:
                pii_map[token_name] = value

        # Extract reference PII (names and emails of references)
        for i, ref in enumerate(resume_data.get("references", []), start=1):
            if ref.get("name"):
                pii_map[f"{_REFERENCE_TOKEN_PREFIX}_{i}_NAME"] = ref["name"]
            if ref.get("email"):
                pii_map[f"{_REFERENCE_TOKEN_PREFIX}_{i}_EMAIL"] = ref["email"]

        # Extract recommender PII
        for i, rec in enumerate(resume_data.get("recommendations", []), start=1):
            if rec.get("from"):
                pii_map[f"{_RECOMMENDER_TOKEN_PREFIX}_{i}_NAME"] = rec["from"]

        # Extract phone number variants (with/without formatting)
        phone = pii_map.get("CANDIDATE_PHONE", "")
        if phone:
            digits_only = re.sub(r"[^\d]", "", phone)
            if digits_only and digits_only != phone:
                pii_map["CANDIDATE_PHONE_DIGITS"] = digits_only

        # Extract name components from full name if not already present
        full_name = pii_map.get("CANDIDATE_NAME", "")
        if full_name and "CANDIDATE_FIRST_NAME" not in pii_map:
            parts = full_name.split()
            if len(parts) >= 2:
                pii_map["CANDIDATE_FIRST_NAME"] = parts[0]
                pii_map["CANDIDATE_LAST_NAME"] = parts[-1]

        logger.info("PIIGuard initialized with %d PII fields", len(pii_map))
        return cls(pii_map)

    @property
    def field_count(self) -> int:
        """Number of PII fields being protected."""
        return len(self._pii_map)

    @property
    def redaction_count(self) -> int:
        """Total number of redactions performed since initialization."""
        return self._redaction_count

    def redact(self, text: str) -> str:
        """Replace all PII in text with tokens.

        Args:
            text: Text that may contain PII

        Returns:
            Text with PII replaced by [TOKEN_NAME] placeholders
        """
        result = text
        count = 0
        for token_name, real_value in self._sorted_tokens:
            if real_value in result:
                occurrences = result.count(real_value)
                result = result.replace(real_value, f"[{token_name}]")
                count += occurrences

        if count > 0:
            self._redaction_count += count
            logger.debug("Redacted %d PII occurrences", count)

        return result

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively redact PII in a dictionary (e.g., master_resume.json).

        Args:
            data: Dictionary that may contain PII values

        Returns:
            New dictionary with PII values replaced by tokens
        """
        return json.loads(self.redact(json.dumps(data)))

    def restore(self, text: str) -> str:
        """Replace tokens in text with real PII values.

        Args:
            text: Text containing [TOKEN_NAME] placeholders (e.g., LLM response)

        Returns:
            Text with tokens replaced by real PII values
        """
        result = text
        for token_name, real_value in self._sorted_tokens:
            token = f"[{token_name}]"
            if token in result:
                result = result.replace(token, real_value)

        return result

    def restore_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively restore tokens in a dictionary.

        Args:
            data: Dictionary with token placeholders

        Returns:
            New dictionary with tokens replaced by real PII values
        """
        return json.loads(self.restore(json.dumps(data)))

    def get_redacted_fields(self) -> list[str]:
        """Return the list of token names being used (for audit logging)."""
        return list(self._pii_map.keys())
