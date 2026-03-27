"""Tests for Phase 8 — Smart Scoring Improvements."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.db.database import (
    get_analysis,
    get_score_calibration,
    init_db,
    save_analysis,
    save_job,
    update_application,
)
from src.models import JobAnalysis, ScorePenalty


@pytest.fixture()
def db(tmp_path):
    """Initialize a fresh test database."""
    db_file = tmp_path / "test_jobs.db"
    with patch("src.db.database.DB_PATH", db_file):
        init_db()
        yield db_file


@pytest.fixture()
def sample_job(db):
    """Save a sample job and return its ID."""
    return save_job(
        {
            "title": "Senior Data Engineer",
            "company": "TestCorp",
            "location": "San Francisco, CA",
            "description": "Build data pipelines.",
            "requirements": ["Python", "Spark", "AWS"],
            "responsibilities": ["Design systems"],
        },
        "https://example.com/job/1",
    )


class TestScorePenaltyModel:
    def test_creates_penalty(self):
        p = ScorePenalty(rule="skill_level_mismatch", points=-20, reason="Needs expert Spark")
        assert p.rule == "skill_level_mismatch"
        assert p.points == -20
        assert p.reason == "Needs expert Spark"

    def test_creates_bonus(self):
        p = ScorePenalty(rule="interest_alignment", points=10, reason="Matches target role")
        assert p.points == 10


class TestJobAnalysisModel:
    def test_with_penalties(self):
        analysis = JobAnalysis(
            fit_score=72,
            base_score=82,
            penalties=[
                ScorePenalty(rule="location_mismatch", points=-10, reason="Not remote"),
            ],
            fit_reasoning="Good match with location penalty.",
            matching_skills=["Python", "SQL"],
            gaps=["Kubernetes"],
            keywords=["data pipeline"],
            tailoring_strategy="Emphasize Python.",
        )
        assert analysis.base_score == 82
        assert len(analysis.penalties) == 1
        assert analysis.fit_score == 72

    def test_without_penalties_backward_compat(self):
        analysis = JobAnalysis(
            fit_score=80,
            fit_reasoning="Good match.",
            matching_skills=["Python"],
            gaps=[],
            keywords=["data"],
            tailoring_strategy="Highlight Python.",
        )
        assert analysis.base_score is None
        assert analysis.penalties == []

    def test_multiple_penalties(self):
        penalties = [
            ScorePenalty(rule="skill_level_mismatch", points=-20, reason="Expert Spark needed"),
            ScorePenalty(rule="location_mismatch", points=-10, reason="On-site only"),
            ScorePenalty(rule="interest_alignment", points=10, reason="Matches target"),
        ]
        analysis = JobAnalysis(
            fit_score=65,
            base_score=85,
            penalties=penalties,
            fit_reasoning="Strong skills but location/level issues.",
            matching_skills=["Python"],
            gaps=["Spark"],
            keywords=["ETL"],
            tailoring_strategy="Focus on experience.",
        )
        assert len(analysis.penalties) == 3
        total_adj = sum(p.points for p in analysis.penalties)
        assert total_adj == -20  # -20 + -10 + 10


class TestSaveAnalysisWithPenalties:
    def test_stores_base_score_and_penalties(self, db, sample_job):
        analysis_data = {
            "fit_score": 72,
            "base_score": 82,
            "penalties": [
                {"rule": "location_mismatch", "points": -10, "reason": "Not in preferred locations"},
            ],
            "fit_reasoning": "Good match overall.",
            "matching_skills": ["Python", "SQL"],
            "gaps": ["Kubernetes"],
            "keywords": ["data"],
            "tailoring_strategy": "Highlight Python.",
        }
        save_analysis(sample_job, analysis_data)

        result = get_analysis(sample_job)
        assert result is not None
        assert result["base_score"] == 82
        assert result["fit_score"] == 72
        assert len(result["penalties"]) == 1
        assert result["penalties"][0]["rule"] == "location_mismatch"

    def test_stores_empty_penalties(self, db, sample_job):
        analysis_data = {
            "fit_score": 90,
            "base_score": 90,
            "penalties": [],
            "fit_reasoning": "Perfect match.",
            "matching_skills": ["Python"],
            "gaps": [],
            "keywords": ["data"],
            "tailoring_strategy": "Strong fit.",
        }
        save_analysis(sample_job, analysis_data)

        result = get_analysis(sample_job)
        assert result["base_score"] == 90
        assert result["penalties"] == []

    def test_backward_compat_no_base_score(self, db, sample_job):
        analysis_data = {
            "fit_score": 80,
            "fit_reasoning": "Good match.",
            "matching_skills": ["Python"],
            "gaps": [],
            "keywords": ["data"],
            "tailoring_strategy": "OK.",
        }
        save_analysis(sample_job, analysis_data)

        result = get_analysis(sample_job)
        assert result["base_score"] is None
        assert result["penalties"] == []

    def test_stores_pydantic_penalties(self, db, sample_job):
        """Test that Pydantic ScorePenalty objects are serialized correctly."""
        penalties = [
            ScorePenalty(rule="overqualification", points=-10, reason="Too senior"),
        ]
        analysis_data = {
            "fit_score": 70,
            "base_score": 80,
            "penalties": penalties,
            "fit_reasoning": "Overqualified.",
            "matching_skills": ["Python"],
            "gaps": [],
            "keywords": ["data"],
            "tailoring_strategy": "Downplay seniority.",
        }
        save_analysis(sample_job, analysis_data)

        result = get_analysis(sample_job)
        assert result["penalties"][0]["rule"] == "overqualification"


class TestScoreCalibration:
    def _create_job_with_outcome(self, db, title, score, status, penalties=None):
        """Helper to create a job, analysis, and application with a specific outcome."""
        job_id = save_job(
            {
                "title": title,
                "company": "TestCorp",
                "location": "Remote",
                "description": "Test job.",
                "requirements": [],
                "responsibilities": [],
            },
            f"https://example.com/job/{title.replace(' ', '-').lower()}",
        )
        analysis_data = {
            "fit_score": score,
            "base_score": score + 5,
            "penalties": penalties or [],
            "fit_reasoning": "Test.",
            "matching_skills": ["Python"],
            "gaps": [],
            "keywords": ["test"],
            "tailoring_strategy": "Test.",
        }
        save_analysis(job_id, analysis_data)
        update_application(job_id, status=status)
        return job_id

    def test_empty_outcomes(self, db):
        cal = get_score_calibration()
        assert cal["total_with_outcomes"] == 0
        assert cal["recommended_threshold"] is None

    def test_avg_by_status(self, db):
        self._create_job_with_outcome(db, "Job A", 85, "interview")
        self._create_job_with_outcome(db, "Job B", 75, "interview")
        self._create_job_with_outcome(db, "Job C", 50, "rejected")
        self._create_job_with_outcome(db, "Job D", 40, "rejected")

        cal = get_score_calibration()
        assert cal["avg_by_status"]["interview"]["avg_score"] == 80.0
        assert cal["avg_by_status"]["rejected"]["avg_score"] == 45.0
        assert cal["avg_by_status"]["interview"]["count"] == 2
        assert cal["avg_by_status"]["rejected"]["count"] == 2

    def test_recommended_threshold(self, db):
        self._create_job_with_outcome(db, "Job A", 80, "interview")
        self._create_job_with_outcome(db, "Job B", 40, "rejected")

        cal = get_score_calibration()
        # Midpoint of 80 (interview avg) and 40 (rejected avg) = 60
        assert cal["recommended_threshold"] == 60

    def test_no_threshold_without_both_statuses(self, db):
        self._create_job_with_outcome(db, "Job A", 80, "interview")
        cal = get_score_calibration()
        assert cal["recommended_threshold"] is None

    def test_penalty_analysis(self, db):
        self._create_job_with_outcome(
            db, "Job A", 50, "rejected",
            penalties=[{"rule": "location_mismatch", "points": -10, "reason": "Not remote"}],
        )
        self._create_job_with_outcome(
            db, "Job B", 45, "rejected",
            penalties=[
                {"rule": "location_mismatch", "points": -10, "reason": "Not remote"},
                {"rule": "skill_level_mismatch", "points": -20, "reason": "Expert needed"},
            ],
        )
        self._create_job_with_outcome(
            db, "Job C", 85, "interview",
            penalties=[{"rule": "interest_alignment", "points": 10, "reason": "Target role"}],
        )

        cal = get_score_calibration()
        assert cal["penalty_analysis"]["rejected"]["location_mismatch"] == 2
        assert cal["penalty_analysis"]["rejected"]["skill_level_mismatch"] == 1
        assert cal["penalty_analysis"]["successful"]["interest_alignment"] == 1

    def test_offer_counted_as_successful(self, db):
        self._create_job_with_outcome(
            db, "Job A", 90, "offer",
            penalties=[{"rule": "interest_alignment", "points": 10, "reason": "Perfect fit"}],
        )

        cal = get_score_calibration()
        assert cal["penalty_analysis"]["successful"]["interest_alignment"] == 1

    def test_total_with_outcomes(self, db):
        self._create_job_with_outcome(db, "Job A", 80, "interview")
        self._create_job_with_outcome(db, "Job B", 70, "applied")
        self._create_job_with_outcome(db, "Job C", 40, "rejected")

        cal = get_score_calibration()
        assert cal["total_with_outcomes"] == 3


class TestPreferencesFormatting:
    """Test that preferences are correctly formatted for the analysis prompt."""

    def test_preferences_extracted_from_resume(self):
        """Verify the preferences formatting logic in analyze_job."""
        resume = {
            "preferences": {
                "target_roles": ["Data Engineer", "ML Engineer"],
                "locations": ["California", "New York"],
                "work_modes": ["remote", "hybrid"],
                "job_types": ["full-time"],
                "min_salary": None,
            }
        }

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

        text = "\n".join(pref_lines)
        assert "Target roles: Data Engineer, ML Engineer" in text
        assert "Preferred locations: California, New York" in text
        assert "Work modes: remote, hybrid" in text
        assert "Job types: full-time" in text
        assert "Minimum salary" not in text  # None should be skipped

    def test_no_preferences(self):
        resume = {}
        prefs = resume.get("preferences", {})
        pref_lines = []
        if prefs.get("target_roles"):
            pref_lines.append(f"Target roles: {', '.join(prefs['target_roles'])}")
        text = "\n".join(pref_lines) if pref_lines else "No preferences specified"
        assert text == "No preferences specified"


class TestDatabaseMigration:
    """Test that the migration adds columns to existing databases."""

    def test_migration_adds_columns(self, tmp_path):
        """Init DB without new columns, then re-init to trigger migration."""
        import sqlite3

        db_file = tmp_path / "migrate_test.db"

        # Create a "legacy" database without the new columns
        conn = sqlite3.connect(str(db_file))
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
                requirements TEXT,
                responsibilities TEXT,
                benefits TEXT,
                application_url TEXT,
                date_posted TEXT,
                scraped_at TEXT NOT NULL,
                raw_markdown TEXT
            );
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL REFERENCES jobs(id),
                fit_score INTEGER NOT NULL,
                fit_reasoning TEXT,
                matching_skills TEXT,
                gaps TEXT,
                keywords TEXT,
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
        """)
        conn.commit()
        conn.close()

        # Now run init_db which should add base_score and penalties columns
        with patch("src.db.database.DB_PATH", db_file):
            init_db()

            # Verify columns were added
            conn = sqlite3.connect(str(db_file))
            cols = {r[1] for r in conn.execute("PRAGMA table_info(analyses)").fetchall()}
            conn.close()
            assert "base_score" in cols
            assert "penalties" in cols
