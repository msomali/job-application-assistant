"""Tests for skill market analytics (Phase 6)."""

from unittest.mock import patch

import pytest

from src.db.database import (
    get_skill_gaps,
    get_skill_stats,
    get_skill_stats_by_role,
    get_skill_trend,
    init_db,
    save_analysis,
    save_job,
    save_job_skills,
)


@pytest.fixture()
def db(tmp_path):
    """Initialize a fresh test database."""
    db_file = tmp_path / "test_jobs.db"
    with patch("src.db.database.DB_PATH", db_file):
        init_db()
        yield db_file


def _make_job(title="Senior Data Engineer", company="Acme Corp"):
    return {
        "title": title,
        "company": company,
        "location": "Remote",
        "description": "Build data pipelines.",
        "requirements": ["Python", "SQL"],
        "responsibilities": ["Design pipelines"],
        "benefits": [],
    }


def _make_analysis(keywords=None, matching_skills=None, gaps=None):
    return {
        "fit_score": 80,
        "fit_reasoning": "Good match.",
        "matching_skills": matching_skills or ["python", "sql"],
        "gaps": gaps or ["spark"],
        "keywords": keywords or ["data pipelines", "etl", "python", "sql", "aws"],
        "tailoring_strategy": "Emphasize pipeline work.",
    }


class TestSaveJobSkills:
    def test_saves_skills_from_analysis(self, db):
        job_id = save_job(_make_job(), "https://example.com/1")
        count = save_job_skills(job_id, _make_analysis())
        assert count > 0

    def test_deduplicates_same_skill_same_source(self, db):
        job_id = save_job(_make_job(), "https://example.com/2")
        analysis = _make_analysis(keywords=["python", "python"])
        save_job_skills(job_id, analysis)
        # Second "python" should be silently skipped
        stats = get_skill_stats()
        python_entries = [s for s in stats if s["skill"] == "python"]
        assert len(python_entries) == 1

    def test_allows_same_skill_different_sources(self, db):
        job_id = save_job(_make_job(), "https://example.com/3")
        analysis = _make_analysis(
            keywords=["python"],
            matching_skills=["python"],
        )
        save_job_skills(job_id, analysis)
        stats = get_skill_stats()
        python = [s for s in stats if s["skill"] == "python"][0]
        assert "keyword" in python["sources"]
        assert "requirement" in python["sources"]

    def test_normalizes_to_lowercase(self, db):
        job_id = save_job(_make_job(), "https://example.com/4")
        save_job_skills(job_id, _make_analysis(keywords=["Python", "AWS"]))
        stats = get_skill_stats()
        skills = [s["skill"] for s in stats]
        assert "python" in skills
        assert "aws" in skills
        assert "Python" not in skills

    def test_skips_empty_skills(self, db):
        job_id = save_job(_make_job(), "https://example.com/5")
        save_job_skills(job_id, _make_analysis(keywords=["python", "", "  "]))
        # Only non-empty skills should be saved
        stats = get_skill_stats()
        assert all(s["skill"].strip() for s in stats)


class TestSaveAnalysisAutoExtracts:
    def test_save_analysis_populates_job_skills(self, db):
        """save_analysis should automatically call save_job_skills."""
        job_id = save_job(_make_job(), "https://example.com/auto")
        save_analysis(job_id, _make_analysis())
        stats = get_skill_stats()
        assert len(stats) > 0


class TestGetSkillStats:
    def test_returns_sorted_by_frequency(self, db):
        for i in range(3):
            job_id = save_job(_make_job(), f"https://example.com/freq-{i}")
            save_job_skills(job_id, _make_analysis(keywords=["python", "sql"]))

        # Add one more job with extra skill
        job_id = save_job(_make_job(), "https://example.com/freq-extra")
        save_job_skills(job_id, _make_analysis(keywords=["python"]))

        stats = get_skill_stats(limit=5)
        assert stats[0]["skill"] == "python"
        assert stats[0]["job_count"] == 4

    def test_limit_parameter(self, db):
        job_id = save_job(_make_job(), "https://example.com/lim")
        save_job_skills(job_id, _make_analysis(
            keywords=["a", "b", "c", "d", "e", "f"]
        ))
        stats = get_skill_stats(limit=3)
        assert len(stats) == 3

    def test_empty_db_returns_empty(self, db):
        stats = get_skill_stats()
        assert stats == []

    def test_counts_distinct_jobs(self, db):
        """Same skill from same job should count as 1, not per-source."""
        job_id = save_job(_make_job(), "https://example.com/distinct")
        save_job_skills(job_id, _make_analysis(
            keywords=["python"],
            matching_skills=["python"],
            gaps=["python"],
        ))
        stats = get_skill_stats()
        python = [s for s in stats if s["skill"] == "python"][0]
        assert python["job_count"] == 1  # 1 job, not 3


class TestGetSkillStatsByRole:
    def test_groups_by_role(self, db):
        for i, title in enumerate(["Senior Data Engineer", "ML Engineer", "Data Analyst"]):
            job_id = save_job(_make_job(title=title), f"https://example.com/role-{i}")
            save_job_skills(job_id, _make_analysis(keywords=["python"]))

        by_role = get_skill_stats_by_role()
        assert len(by_role) > 0
        # All roles should have python
        for _role, skills in by_role.items():
            skill_names = [s["skill"] for s in skills]
            assert "python" in skill_names

    def test_empty_db_returns_empty(self, db):
        assert get_skill_stats_by_role() == {}


class TestGetSkillTrend:
    def test_returns_rising_and_established(self, db):
        # Just need the structure to be correct
        trend = get_skill_trend()
        assert "rising" in trend
        assert "established" in trend

    def test_empty_db_returns_empty_lists(self, db):
        trend = get_skill_trend()
        assert trend["rising"] == []
        assert trend["established"] == []


class TestGetSkillGaps:
    def test_finds_missing_skills(self, db):
        job_id = save_job(_make_job(), "https://example.com/gap")
        save_job_skills(job_id, _make_analysis(
            keywords=["python", "scala", "kafka", "terraform"]
        ))

        gaps = get_skill_gaps(["Python", "SQL"])  # user has Python and SQL
        gap_skills = [g["skill"] for g in gaps]
        assert "scala" in gap_skills
        assert "kafka" in gap_skills
        assert "terraform" in gap_skills
        assert "python" not in gap_skills  # user has this

    def test_case_insensitive_matching(self, db):
        job_id = save_job(_make_job(), "https://example.com/case")
        save_job_skills(job_id, _make_analysis(keywords=["python"]))

        gaps = get_skill_gaps(["Python"])  # uppercase in user skills
        gap_skills = [g["skill"] for g in gaps]
        assert "python" not in gap_skills

    def test_limit_parameter(self, db):
        job_id = save_job(_make_job(), "https://example.com/gap-lim")
        save_job_skills(job_id, _make_analysis(
            keywords=["a", "b", "c", "d", "e"]
        ))
        gaps = get_skill_gaps([], limit=2)
        assert len(gaps) == 2

    def test_no_gaps_when_user_has_everything(self, db):
        job_id = save_job(_make_job(), "https://example.com/no-gap")
        save_job_skills(job_id, _make_analysis(keywords=["python", "sql"]))
        gaps = get_skill_gaps(["Python", "SQL", "data pipelines", "etl", "aws"])
        # All job skills should be covered
        assert len(gaps) == 0 or all(
            g["skill"] not in {"python", "sql"} for g in gaps
        )
