"""Tests for the PII Guard privacy module."""

import json
from pathlib import Path

import pytest

from src.privacy.pii_guard import PIIGuard


@pytest.fixture()
def sample_resume(tmp_path):
    """Create a minimal master_resume.json for testing."""
    resume = {
        "name": "John Doe",
        "contact": "Los Angeles, CA | john.doe@example.com | +1-555-123-4567 | linkedin.com/in/johndoe | github.com/johndoe",
        "summary": "Data Engineer with experience.",
        "experience": [
            {
                "title": "Data Analyst",
                "company": "Acme Corp",
                "bullets": ["Built pipelines for John Doe's team."],
            }
        ],
        "references": [
            {"name": "Jane Smith", "email": "jane.smith@company.com"},
            {"name": "Bob Wilson", "email": "bob.wilson@uni.edu"},
        ],
        "recommendations": [
            {"from": "Alice Johnson", "quote": "John is great."},
        ],
    }
    path = tmp_path / "master_resume.json"
    path.write_text(json.dumps(resume))
    return path


@pytest.fixture()
def sample_screening(tmp_path):
    """Create a minimal screening_answers.json for testing."""
    screening = {
        "personal": {
            "full_name": "John Doe",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "phone": "+1-555-123-4567",
            "linkedin": "https://linkedin.com/in/johndoe",
            "github": "https://github.com/johndoe",
            "zip_code": "90040",
            "preferred_name": "John",
            "website": "",
        }
    }
    path = tmp_path / "screening_answers.json"
    path.write_text(json.dumps(screening))
    return path


@pytest.fixture()
def guard(sample_resume, sample_screening):
    """Create a PIIGuard from test fixtures."""
    return PIIGuard.from_files(sample_resume, sample_screening)


class TestPIIGuardInit:
    def test_from_files_loads_fields(self, guard):
        assert guard.field_count > 0
        fields = guard.get_redacted_fields()
        assert "CANDIDATE_NAME" in fields
        assert "CANDIDATE_EMAIL" in fields
        assert "CANDIDATE_PHONE" in fields

    def test_from_files_loads_references(self, guard):
        fields = guard.get_redacted_fields()
        assert "REFERENCE_1_NAME" in fields
        assert "REFERENCE_1_EMAIL" in fields
        assert "REFERENCE_2_NAME" in fields

    def test_from_files_loads_recommenders(self, guard):
        fields = guard.get_redacted_fields()
        assert "RECOMMENDER_1_NAME" in fields

    def test_from_files_extracts_phone_digits(self, guard):
        fields = guard.get_redacted_fields()
        assert "CANDIDATE_PHONE_DIGITS" in fields

    def test_from_files_missing_screening(self, sample_resume):
        guard = PIIGuard.from_files(sample_resume)
        assert guard.field_count > 0

    def test_from_files_missing_resume(self, tmp_path):
        fake_path = tmp_path / "nonexistent.json"
        guard = PIIGuard.from_files(fake_path)
        assert guard.field_count == 0

    def test_empty_values_excluded(self):
        guard = PIIGuard({"NAME": "John", "EMPTY": "", "WHITESPACE": "  "})
        assert guard.field_count == 1


class TestRedaction:
    def test_redacts_name(self, guard):
        text = "The candidate John Doe has great skills."
        result = guard.redact(text)
        assert "John Doe" not in result
        assert "[CANDIDATE_NAME]" in result

    def test_redacts_email(self, guard):
        text = "Contact me at john.doe@example.com for details."
        result = guard.redact(text)
        assert "john.doe@example.com" not in result
        assert "[CANDIDATE_EMAIL]" in result

    def test_redacts_phone(self, guard):
        text = "Call me at +1-555-123-4567."
        result = guard.redact(text)
        assert "+1-555-123-4567" not in result
        assert "[CANDIDATE_PHONE]" in result

    def test_redacts_linkedin(self, guard):
        text = "Profile: https://linkedin.com/in/johndoe"
        result = guard.redact(text)
        assert "linkedin.com/in/johndoe" not in result
        assert "[CANDIDATE_LINKEDIN]" in result

    def test_redacts_github(self, guard):
        text = "Code: https://github.com/johndoe"
        result = guard.redact(text)
        assert "github.com/johndoe" not in result
        assert "[CANDIDATE_GITHUB]" in result

    def test_redacts_reference_names(self, guard):
        text = "Reference: Jane Smith at company.com"
        result = guard.redact(text)
        assert "Jane Smith" not in result
        assert "[REFERENCE_1_NAME]" in result

    def test_redacts_reference_emails(self, guard):
        text = "Contact jane.smith@company.com for reference."
        result = guard.redact(text)
        assert "jane.smith@company.com" not in result
        assert "[REFERENCE_1_EMAIL]" in result

    def test_redacts_multiple_occurrences(self, guard):
        text = "John Doe applied. John Doe is qualified."
        result = guard.redact(text)
        assert result.count("[CANDIDATE_NAME]") == 2
        assert "John Doe" not in result

    def test_non_pii_preserved(self, guard):
        text = "Python, SQL, and PySpark are required skills."
        result = guard.redact(text)
        assert result == text

    def test_longer_values_replaced_first(self, guard):
        """Full name should be replaced before first/last name fragments."""
        text = "John Doe is the candidate."
        result = guard.redact(text)
        assert "[CANDIDATE_NAME]" in result
        # Should NOT have partial replacements like [CANDIDATE_FIRST_NAME] Doe
        assert "Doe" not in result or "[CANDIDATE_NAME]" in result

    def test_redaction_count_tracking(self, guard):
        assert guard.redaction_count == 0
        guard.redact("John Doe at john.doe@example.com")
        assert guard.redaction_count > 0


class TestRedactDict:
    def test_redacts_nested_dict(self, guard):
        data = {
            "name": "John Doe",
            "contact": {"email": "john.doe@example.com", "phone": "+1-555-123-4567"},
        }
        result = guard.redact_dict(data)
        assert result["name"] == "[CANDIDATE_NAME]"
        assert result["contact"]["email"] == "[CANDIDATE_EMAIL]"
        assert result["contact"]["phone"] == "[CANDIDATE_PHONE]"

    def test_original_unchanged(self, guard):
        data = {"name": "John Doe"}
        guard.redact_dict(data)
        assert data["name"] == "John Doe"


class TestRestoration:
    def test_restores_name(self, guard):
        text = "The candidate [CANDIDATE_NAME] has great skills."
        result = guard.restore(text)
        assert result == "The candidate John Doe has great skills."

    def test_restores_email(self, guard):
        text = "Email: [CANDIDATE_EMAIL]"
        result = guard.restore(text)
        assert result == "Email: john.doe@example.com"

    def test_restores_all_tokens(self, guard):
        text = "[CANDIDATE_NAME] - [CANDIDATE_EMAIL] - [CANDIDATE_PHONE]"
        result = guard.restore(text)
        assert "John Doe" in result
        assert "john.doe@example.com" in result
        assert "+1-555-123-4567" in result

    def test_restores_reference_tokens(self, guard):
        text = "Reference: [REFERENCE_1_NAME] ([REFERENCE_1_EMAIL])"
        result = guard.restore(text)
        assert "Jane Smith" in result
        assert "jane.smith@company.com" in result

    def test_non_token_text_preserved(self, guard):
        text = "Python and SQL are great."
        result = guard.restore(text)
        assert result == text


class TestRestoreDict:
    def test_restores_nested_dict(self, guard):
        data = {
            "name": "[CANDIDATE_NAME]",
            "contact": {"email": "[CANDIDATE_EMAIL]"},
        }
        result = guard.restore_dict(data)
        assert result["name"] == "John Doe"
        assert result["contact"]["email"] == "john.doe@example.com"


class TestRoundTrip:
    def test_redact_then_restore(self, guard):
        original = "John Doe (john.doe@example.com, +1-555-123-4567)"
        redacted = guard.redact(original)
        restored = guard.restore(redacted)
        assert restored == original

    def test_dict_round_trip(self, guard):
        original = {
            "name": "John Doe",
            "email": "john.doe@example.com",
            "skills": ["Python", "SQL"],
        }
        redacted = guard.redact_dict(original)
        restored = guard.restore_dict(redacted)
        assert restored == original

    def test_contact_string_round_trip(self, guard):
        """Test with a contact string similar to the real master_resume."""
        original = "Los Angeles, CA | john.doe@example.com | +1-555-123-4567 | linkedin.com/in/johndoe | github.com/johndoe"
        redacted = guard.redact(original)
        assert "john.doe@example.com" not in redacted
        assert "+1-555-123-4567" not in redacted
        restored = guard.restore(redacted)
        assert restored == original


class TestFromRealFiles:
    """Test with actual project data files if available."""

    def test_loads_real_resume(self):
        resume_path = Path(__file__).parent.parent.parent / "data" / "master_resume.json"
        screening_path = Path(__file__).parent.parent.parent / "data" / "screening_answers.json"
        if not resume_path.exists():
            pytest.skip("Real data files not available")

        guard = PIIGuard.from_files(resume_path, screening_path)
        assert guard.field_count > 0

        resume = json.loads(resume_path.read_text())
        name = resume.get("name", "")

        redacted = guard.redact(name)
        assert name not in redacted
        assert "[CANDIDATE_NAME]" in redacted

        restored = guard.restore(redacted)
        assert restored == name
