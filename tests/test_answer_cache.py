"""Tests for the answer learning/caching system (Phase 7)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.db.database import (
    delete_answer,
    find_answer,
    find_answer_fuzzy,
    get_answer_stats,
    import_screening_answers,
    init_db,
    list_answers,
    save_answer,
)


@pytest.fixture()
def db(tmp_path):
    """Initialize a fresh test database."""
    db_file = tmp_path / "test_jobs.db"
    with patch("src.db.database.DB_PATH", db_file):
        init_db()
        yield db_file


@pytest.fixture()
def screening_file(tmp_path):
    """Create a test screening_answers.json."""
    data = {
        "personal": {
            "full_name": "John Doe",
            "email": "john@example.com",
            "phone": "+1-555-0100",
        },
        "work_authorization": {
            "authorized_to_work_in_us": True,
            "require_sponsorship": False,
            "visa_status": "US Citizen",
        },
        "experience": {
            "total_years_experience": "5+",
            "years_python": "4+",
        },
        "common_questions": {
            "why_interested": "I love building data systems.",
            "greatest_strength": "Problem solving.",
            "_note": "This should be skipped",
        },
    }
    path = tmp_path / "screening_answers.json"
    path.write_text(json.dumps(data))
    return path


class TestSaveAnswer:
    def test_saves_new_answer(self, db):
        answer_id = save_answer("What is your name?", "John Doe")
        assert answer_id > 0

    def test_returns_id_on_update(self, db):
        id1 = save_answer("What is your name?", "John Doe")
        id2 = save_answer("What is your name?", "Jane Doe")
        assert id1 == id2  # same question, updates in place

    def test_updates_answer_value(self, db):
        save_answer("What is your name?", "John Doe")
        save_answer("What is your name?", "Jane Doe")
        result = find_answer("What is your name?")
        assert result["answer"] == "Jane Doe"

    def test_saves_with_category(self, db):
        save_answer("Years of Python?", "5+", category="experience")
        result = find_answer("Years of Python?")
        assert result["category"] == "experience"

    def test_saves_with_source(self, db):
        save_answer("Visa status?", "US Citizen", source="imported")
        result = find_answer("Visa status?")
        assert result["source"] == "imported"


class TestFindAnswer:
    def test_finds_exact_match(self, db):
        save_answer("What is your email?", "john@example.com")
        result = find_answer("What is your email?")
        assert result is not None
        assert result["answer"] == "john@example.com"

    def test_normalizes_question(self, db):
        save_answer("What is your email?", "john@example.com")
        # Should match with different casing, extra whitespace, trailing punctuation
        result = find_answer("  WHAT IS YOUR EMAIL?  ")
        assert result is not None
        assert result["answer"] == "john@example.com"

    def test_strips_trailing_punctuation(self, db):
        save_answer("What is your name", "John Doe")
        result = find_answer("What is your name?")
        assert result is not None

    def test_returns_none_for_missing(self, db):
        result = find_answer("Nonexistent question")
        assert result is None

    def test_increments_usage_count(self, db):
        save_answer("What is your name?", "John Doe")

        find_answer("What is your name?")
        find_answer("What is your name?")
        find_answer("What is your name?")

        answers = list_answers()
        assert answers[0]["times_used"] == 3

    def test_updates_last_used_at(self, db):
        save_answer("What is your name?", "John Doe")
        find_answer("What is your name?")
        answers = list_answers()
        assert answers[0]["last_used_at"] is not None


class TestFindAnswerFuzzy:
    def test_exact_match_preferred(self, db):
        save_answer("What is your email address?", "john@example.com")
        result = find_answer_fuzzy("What is your email address?")
        assert result is not None
        assert "_fuzzy_score" not in result

    def test_fuzzy_matches_similar_question(self, db):
        save_answer("What is your email address?", "john@example.com")
        result = find_answer_fuzzy("What is your email?")
        assert result is not None
        assert result["answer"] == "john@example.com"
        assert "_fuzzy_score" in result

    def test_rejects_low_similarity(self, db):
        save_answer("What is your email address?", "john@example.com")
        result = find_answer_fuzzy("What color is the sky?")
        assert result is None

    def test_custom_threshold(self, db):
        save_answer("Years of Python experience?", "5+")
        # With low threshold, should match loosely
        result = find_answer_fuzzy("Python years of experience?", threshold=0.5)
        assert result is not None

    def test_increments_usage_on_fuzzy(self, db):
        save_answer("What is your email address?", "john@example.com")
        find_answer_fuzzy("What is your email?")
        answers = list_answers()
        assert answers[0]["times_used"] == 1


class TestListAnswers:
    def test_lists_all(self, db):
        save_answer("Q1?", "A1")
        save_answer("Q2?", "A2")
        save_answer("Q3?", "A3")
        assert len(list_answers()) == 3

    def test_filters_by_category(self, db):
        save_answer("Q1?", "A1", category="personal")
        save_answer("Q2?", "A2", category="experience")
        save_answer("Q3?", "A3", category="personal")
        result = list_answers(category="personal")
        assert len(result) == 2

    def test_filters_by_source(self, db):
        save_answer("Q1?", "A1", source="manual")
        save_answer("Q2?", "A2", source="imported")
        result = list_answers(source="manual")
        assert len(result) == 1

    def test_ordered_by_usage(self, db):
        save_answer("Q1?", "A1")
        save_answer("Q2?", "A2")
        # Use Q2 more
        find_answer("Q2?")
        find_answer("Q2?")
        result = list_answers()
        assert result[0]["question"] == "q2"

    def test_limit_parameter(self, db):
        for i in range(10):
            save_answer(f"Q{i}?", f"A{i}")
        assert len(list_answers(limit=3)) == 3

    def test_empty_db(self, db):
        assert list_answers() == []


class TestDeleteAnswer:
    def test_deletes_existing(self, db):
        answer_id = save_answer("Q1?", "A1")
        assert delete_answer(answer_id) is True
        assert find_answer("Q1?") is None

    def test_returns_false_for_missing(self, db):
        assert delete_answer(999) is False


class TestGetAnswerStats:
    def test_empty_db(self, db):
        stats = get_answer_stats()
        assert stats["total_answers"] == 0
        assert stats["total_lookups"] == 0

    def test_counts_correctly(self, db):
        save_answer("Q1?", "A1", source="manual", category="personal")
        save_answer("Q2?", "A2", source="imported", category="experience")
        save_answer("Q3?", "A3", source="manual", category="personal")

        find_answer("Q1?")
        find_answer("Q1?")

        stats = get_answer_stats()
        assert stats["total_answers"] == 3
        assert stats["total_lookups"] == 2
        assert stats["by_source"]["manual"] == 2
        assert stats["by_source"]["imported"] == 1
        assert stats["by_category"]["personal"] == 2
        assert stats["never_used"] == 2  # Q2 and Q3

    def test_most_used_list(self, db):
        save_answer("Q1?", "A1")
        find_answer("Q1?")
        stats = get_answer_stats()
        assert len(stats["most_used"]) == 1
        assert stats["most_used"][0]["times_used"] == 1


class TestImportScreeningAnswers:
    def test_imports_from_file(self, db, screening_file):
        count = import_screening_answers(screening_file)
        assert count > 0
        # Check a specific imported answer
        result = find_answer("full name")
        assert result is not None
        assert result["answer"] == "John Doe"
        assert result["source"] == "imported"

    def test_sets_category(self, db, screening_file):
        import_screening_answers(screening_file)
        result = find_answer("full name")
        assert result["category"] == "personal"

    def test_skips_underscore_keys(self, db, screening_file):
        import_screening_answers(screening_file)
        result = find_answer("note")
        assert result is None

    def test_converts_booleans(self, db, screening_file):
        import_screening_answers(screening_file)
        result = find_answer("authorized to work in us")
        assert result["answer"] == "Yes"
        result2 = find_answer("require sponsorship")
        assert result2["answer"] == "No"

    def test_idempotent(self, db, screening_file):
        count1 = import_screening_answers(screening_file)
        count2 = import_screening_answers(screening_file)
        assert count1 > 0
        assert count2 == 0  # no new imports on second run

    def test_missing_file_returns_zero(self, db, tmp_path):
        count = import_screening_answers(tmp_path / "nonexistent.json")
        assert count == 0

    def test_skips_empty_values(self, db, tmp_path):
        data = {"personal": {"name": "John", "empty_field": "", "null_field": None}}
        path = tmp_path / "screening.json"
        path.write_text(json.dumps(data))
        count = import_screening_answers(path)
        # Only "name" should be imported
        assert count == 1


class TestNormalization:
    """Test that question normalization is consistent across operations."""

    def test_case_insensitive(self, db):
        save_answer("YEARS OF PYTHON", "5+")
        assert find_answer("years of python") is not None

    def test_whitespace_normalized(self, db):
        save_answer("years   of   python", "5+")
        assert find_answer("years of python") is not None

    def test_trailing_punctuation_stripped(self, db):
        save_answer("years of python?", "5+")
        assert find_answer("years of python") is not None
        assert find_answer("years of python??") is not None
        assert find_answer("years of python!") is not None

    def test_different_questions_stay_separate(self, db):
        save_answer("years of python", "5+")
        save_answer("years of java", "3+")
        assert find_answer("years of python")["answer"] == "5+"
        assert find_answer("years of java")["answer"] == "3+"
