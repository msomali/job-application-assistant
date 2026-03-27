"""Tests for database operations in src/db/database.py."""

import json
from unittest.mock import patch

from src.db import database as db

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

JOB_URL = "https://example.com/jobs/senior-data-engineer"
JOB_URL_2 = "https://example.com/jobs/ml-engineer"


def _insert_job(job_data, url=JOB_URL, raw_markdown=None):
    """Convenience wrapper that patches DB_PATH consistently."""
    return db.save_job(job_data, url, raw_markdown)


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------


class TestInitDb:
    def test_creates_tables(self, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            conn = db.get_connection()
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            conn.close()
            table_names = {t["name"] for t in tables}
            assert "jobs" in table_names
            assert "analyses" in table_names
            assert "applications" in table_names

    def test_idempotent(self, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            db.init_db()  # second call should not raise
            conn = db.get_connection()
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            conn.close()
            assert len(tables) >= 3


# ---------------------------------------------------------------------------
# save_job
# ---------------------------------------------------------------------------


class TestSaveJob:
    def test_inserts_and_returns_id(self, tmp_db, sample_job_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            job_id = _insert_job(sample_job_data)
            assert isinstance(job_id, int)
            assert job_id >= 1

    def test_duplicate_url_returns_existing_id(self, tmp_db, sample_job_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            id1 = _insert_job(sample_job_data, url=JOB_URL)
            id2 = _insert_job(sample_job_data, url=JOB_URL)
            assert id1 == id2

    def test_different_urls_get_different_ids(self, tmp_db, sample_job_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            id1 = _insert_job(sample_job_data, url=JOB_URL)
            id2 = _insert_job(sample_job_data, url=JOB_URL_2)
            assert id1 != id2

    def test_stores_raw_markdown(self, tmp_db, sample_job_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            md = "# Senior Data Engineer\n\nGreat job!"
            job_id = _insert_job(sample_job_data, raw_markdown=md)
            conn = db.get_connection()
            row = conn.execute(
                "SELECT raw_markdown FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            conn.close()
            assert row["raw_markdown"] == md

    def test_json_arrays_stored(self, tmp_db, sample_job_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            job_id = _insert_job(sample_job_data)
            conn = db.get_connection()
            row = conn.execute(
                "SELECT requirements, responsibilities, benefits FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            conn.close()
            reqs = json.loads(row["requirements"])
            assert isinstance(reqs, list)
            assert len(reqs) == 5


# ---------------------------------------------------------------------------
# get_job
# ---------------------------------------------------------------------------


class TestGetJob:
    def test_returns_correct_data(self, tmp_db, sample_job_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            job_id = _insert_job(sample_job_data)
            job = db.get_job(job_id)
            assert job is not None
            assert job["title"] == "Senior Data Engineer"
            assert job["company"] == "Acme Corp"

    def test_json_fields_parsed(self, tmp_db, sample_job_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            job_id = _insert_job(sample_job_data)
            job = db.get_job(job_id)
            assert isinstance(job["requirements"], list)
            assert isinstance(job["responsibilities"], list)
            assert isinstance(job["benefits"], list)

    def test_not_found_returns_none(self, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            assert db.get_job(9999) is None


# ---------------------------------------------------------------------------
# save_analysis / get_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_save_analysis_returns_id(self, tmp_db, sample_job_data, sample_analysis_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            job_id = _insert_job(sample_job_data)
            analysis_id = db.save_analysis(job_id, sample_analysis_data)
            assert isinstance(analysis_id, int)
            assert analysis_id >= 1

    def test_get_analysis_returns_data(self, tmp_db, sample_job_data, sample_analysis_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            job_id = _insert_job(sample_job_data)
            db.save_analysis(job_id, sample_analysis_data)
            analysis = db.get_analysis(job_id)
            assert analysis is not None
            assert analysis["fit_score"] == 85
            assert isinstance(analysis["matching_skills"], list)
            assert isinstance(analysis["gaps"], list)
            assert isinstance(analysis["keywords"], list)

    def test_get_analysis_not_found(self, tmp_db, sample_job_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            job_id = _insert_job(sample_job_data)
            assert db.get_analysis(job_id) is None

    def test_get_analysis_returns_latest(self, tmp_db, sample_job_data, sample_analysis_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            job_id = _insert_job(sample_job_data)
            db.save_analysis(job_id, sample_analysis_data)
            updated = {**sample_analysis_data, "fit_score": 92}
            db.save_analysis(job_id, updated)
            analysis = db.get_analysis(job_id)
            assert analysis["fit_score"] == 92


# ---------------------------------------------------------------------------
# update_application / get_application
# ---------------------------------------------------------------------------


class TestApplication:
    def test_update_creates_new_record(self, tmp_db, sample_job_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            job_id = _insert_job(sample_job_data)
            db.update_application(job_id, status="docs_generated")
            app = db.get_application(job_id)
            assert app is not None
            assert app["status"] == "docs_generated"
            assert app["job_id"] == job_id

    def test_update_existing_record(self, tmp_db, sample_job_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            job_id = _insert_job(sample_job_data)
            db.update_application(job_id, status="discovered")
            db.update_application(job_id, status="applied")
            app = db.get_application(job_id)
            assert app["status"] == "applied"

    def test_update_with_paths(self, tmp_db, sample_job_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            job_id = _insert_job(sample_job_data)
            db.update_application(
                job_id,
                status="docs_generated",
                resume_path="/output/resume.pdf",
                cover_letter_path="/output/cover_letter.pdf",
            )
            app = db.get_application(job_id)
            assert app["resume_path"] == "/output/resume.pdf"
            assert app["cover_letter_path"] == "/output/cover_letter.pdf"

    def test_get_application_not_found(self, tmp_db, sample_job_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            job_id = _insert_job(sample_job_data)
            assert db.get_application(job_id) is None


# ---------------------------------------------------------------------------
# list_jobs
# ---------------------------------------------------------------------------


class TestListJobs:
    def test_empty_database(self, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            jobs = db.list_jobs()
            assert jobs == []

    def test_returns_correct_count(self, tmp_db, sample_job_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            for i in range(5):
                _insert_job(sample_job_data, url=f"https://example.com/job/{i}")
            jobs = db.list_jobs(limit=20)
            assert len(jobs) == 5

    def test_limit_parameter(self, tmp_db, sample_job_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            for i in range(5):
                _insert_job(sample_job_data, url=f"https://example.com/job/{i}")
            jobs = db.list_jobs(limit=3)
            assert len(jobs) == 3

    def test_includes_fit_score_and_status(self, tmp_db, sample_job_data, sample_analysis_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            job_id = _insert_job(sample_job_data)
            db.save_analysis(job_id, sample_analysis_data)
            db.update_application(job_id, status="applied")
            jobs = db.list_jobs()
            assert len(jobs) == 1
            assert jobs[0]["fit_score"] == 85
            assert jobs[0]["status"] == "applied"

    def test_ordering_by_fit_score(self, tmp_db, sample_job_data, sample_analysis_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            id1 = _insert_job(sample_job_data, url="https://example.com/job/1")
            id2 = _insert_job(sample_job_data, url="https://example.com/job/2")
            db.save_analysis(id1, {**sample_analysis_data, "fit_score": 60})
            db.save_analysis(id2, {**sample_analysis_data, "fit_score": 95})
            jobs = db.list_jobs()
            assert jobs[0]["fit_score"] == 95
            assert jobs[1]["fit_score"] == 60


# ---------------------------------------------------------------------------
# get_analytics
# ---------------------------------------------------------------------------


class TestGetAnalytics:
    def test_empty_database(self, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            stats = db.get_analytics()
            assert stats["total_discovered"] == 0
            assert stats["analyzed"] == 0
            assert stats["applied"] == 0
            assert "conversion" in stats
            assert "avg_scores_by_status" in stats

    def test_correct_structure(self, tmp_db, sample_job_data, sample_analysis_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            job_id = _insert_job(sample_job_data)
            db.save_analysis(job_id, sample_analysis_data)
            db.update_application(job_id, status="applied")

            stats = db.get_analytics()
            assert stats["total_discovered"] == 1
            assert stats["analyzed"] == 1
            assert stats["applied"] == 1
            assert "conversion" in stats
            assert "discover_to_docs" in stats["conversion"]
            assert "docs_to_applied" in stats["conversion"]
            assert "applied_to_interview" in stats["conversion"]
            assert "interview_to_offer" in stats["conversion"]

    def test_avg_scores_by_status(self, tmp_db, sample_job_data, sample_analysis_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            job_id = _insert_job(sample_job_data)
            db.save_analysis(job_id, sample_analysis_data)
            db.update_application(job_id, status="applied")

            stats = db.get_analytics()
            avg = stats["avg_scores_by_status"]
            assert "applied" in avg
            assert avg["applied"] == 85.0

    def test_multiple_statuses(self, tmp_db, sample_job_data, sample_analysis_data):
        with patch("src.db.database.DB_PATH", tmp_db):
            id1 = _insert_job(sample_job_data, url="https://example.com/1")
            id2 = _insert_job(sample_job_data, url="https://example.com/2")
            _insert_job(sample_job_data, url="https://example.com/3")
            db.save_analysis(id1, {**sample_analysis_data, "fit_score": 90})
            db.save_analysis(id2, {**sample_analysis_data, "fit_score": 75})
            db.update_application(id1, status="applied")
            db.update_application(id2, status="docs_generated")
            # id3 has no application

            stats = db.get_analytics()
            assert stats["total_discovered"] == 3
            assert stats["analyzed"] == 2
            assert stats["applied"] == 1
            assert stats["docs_generated"] == 1
