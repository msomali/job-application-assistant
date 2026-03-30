"""Tests for collection mode (collect, review, approve, reject) in the database layer."""

from unittest.mock import patch

import pytest

from src.db.database import (
    bulk_collect,
    get_application,
    get_collected_jobs,
    get_uncollected_jobs,
    init_db,
    save_analysis,
    save_job,
    update_application,
)


@pytest.fixture()
def seeded_db(tmp_db, sample_job_data, sample_analysis_data):
    """Database with 3 jobs: two analyzed (scores 85 and 55), one unanalyzed."""
    with patch("src.db.database.DB_PATH", tmp_db):
        # Job 1: high score
        j1 = save_job(sample_job_data, "https://example.com/job1", "# Job 1")
        save_analysis(j1, sample_analysis_data)

        # Job 2: low score
        low_analysis = {**sample_analysis_data, "fit_score": 55}
        j2_data = {**sample_job_data, "title": "Junior Engineer", "company": "SmallCo"}
        j2 = save_job(j2_data, "https://example.com/job2", "# Job 2")
        save_analysis(j2, low_analysis)

        # Job 3: no analysis
        j3_data = {**sample_job_data, "title": "Intern", "company": "StartupCo"}
        j3 = save_job(j3_data, "https://example.com/job3", "# Job 3")

        yield {"job1": j1, "job2": j2, "job3": j3}


class TestGetUncollectedJobs:
    def test_returns_analyzed_jobs(self, seeded_db, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            jobs = get_uncollected_jobs(min_score=0)
            assert len(jobs) == 2  # Only analyzed jobs
            assert jobs[0]["fit_score"] >= jobs[1]["fit_score"]  # Sorted desc

    def test_min_score_filter(self, seeded_db, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            jobs = get_uncollected_jobs(min_score=70)
            assert len(jobs) == 1
            assert jobs[0]["fit_score"] == 85

    def test_excludes_already_collected(self, seeded_db, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            bulk_collect([seeded_db["job1"]])
            jobs = get_uncollected_jobs(min_score=0)
            ids = [j["id"] for j in jobs]
            assert seeded_db["job1"] not in ids


class TestBulkCollect:
    def test_collects_multiple(self, seeded_db, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            count = bulk_collect([seeded_db["job1"], seeded_db["job2"]])
            assert count == 2

            app1 = get_application(seeded_db["job1"])
            app2 = get_application(seeded_db["job2"])
            assert app1["status"] == "collected"
            assert app2["status"] == "collected"

    def test_updates_existing_application(self, seeded_db, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            update_application(seeded_db["job1"], status="discovered")
            bulk_collect([seeded_db["job1"]])
            app = get_application(seeded_db["job1"])
            assert app["status"] == "collected"


class TestGetCollectedJobs:
    def test_returns_only_collected(self, seeded_db, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            bulk_collect([seeded_db["job1"]])
            collected = get_collected_jobs()
            assert len(collected) == 1
            assert collected[0]["id"] == seeded_db["job1"]

    def test_includes_analysis_fields(self, seeded_db, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            bulk_collect([seeded_db["job1"]])
            collected = get_collected_jobs()
            job = collected[0]
            assert "fit_score" in job
            assert "matching_skills" in job
            assert isinstance(job["matching_skills"], list)
            assert "tailoring_strategy" in job

    def test_min_score_filter(self, seeded_db, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            bulk_collect([seeded_db["job1"], seeded_db["job2"]])
            collected = get_collected_jobs(min_score=70)
            assert len(collected) == 1
            assert collected[0]["fit_score"] == 85

    def test_empty_when_none_collected(self, seeded_db, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            collected = get_collected_jobs()
            assert collected == []


class TestRejectFlow:
    def test_reject_sets_status(self, seeded_db, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            bulk_collect([seeded_db["job1"]])
            update_application(seeded_db["job1"], status="rejected")
            app = get_application(seeded_db["job1"])
            assert app["status"] == "rejected"

    def test_rejected_not_in_collected(self, seeded_db, tmp_db):
        with patch("src.db.database.DB_PATH", tmp_db):
            bulk_collect([seeded_db["job1"], seeded_db["job2"]])
            update_application(seeded_db["job1"], status="rejected")
            collected = get_collected_jobs()
            ids = [j["id"] for j in collected]
            assert seeded_db["job1"] not in ids
            assert seeded_db["job2"] in ids
