"""Tests for Pydantic models in src/models.py."""

import pytest
from pydantic import ValidationError

from src.models import CoverLetterContent, JobAnalysis, JobPosting, ResumeContent

# ---------------------------------------------------------------------------
# JobPosting
# ---------------------------------------------------------------------------


class TestJobPosting:
    def test_valid_creation(self, sample_job_data):
        job = JobPosting(**sample_job_data)
        assert job.title == "Senior Data Engineer"
        assert job.company == "Acme Corp"
        assert job.location == "San Francisco, CA (Remote)"
        assert job.salary_range == "$150,000 - $200,000"
        assert job.job_type == "full-time"
        assert job.experience_level == "senior"
        assert len(job.requirements) == 5
        assert len(job.responsibilities) == 4
        assert len(job.benefits) == 4
        assert job.application_url == "https://acme.com/careers/senior-data-engineer"
        assert job.date_posted == "2026-03-15"

    def test_minimal_required_fields(self):
        job = JobPosting(
            title="Software Engineer",
            company="TestCo",
            location="Remote",
            description="Build things.",
        )
        assert job.title == "Software Engineer"
        assert job.salary_range is None
        assert job.job_type is None
        assert job.experience_level is None
        assert job.requirements == []
        assert job.responsibilities == []
        assert job.benefits == []
        assert job.application_url is None
        assert job.date_posted is None

    def test_missing_required_title_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            JobPosting(company="X", location="Y", description="Z")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("title",) for e in errors)

    def test_missing_required_company_raises(self):
        with pytest.raises(ValidationError):
            JobPosting(title="X", location="Y", description="Z")

    def test_missing_required_location_raises(self):
        with pytest.raises(ValidationError):
            JobPosting(title="X", company="Y", description="Z")

    def test_missing_required_description_raises(self):
        with pytest.raises(ValidationError):
            JobPosting(title="X", company="Y", location="Z")

    def test_optional_fields_accept_none(self):
        job = JobPosting(
            title="QA",
            company="C",
            location="L",
            description="D",
            salary_range=None,
            job_type=None,
            experience_level=None,
            application_url=None,
            date_posted=None,
        )
        assert job.salary_range is None

    def test_model_dump_roundtrip(self, sample_job_data):
        job = JobPosting(**sample_job_data)
        dumped = job.model_dump()
        restored = JobPosting(**dumped)
        assert restored == job


# ---------------------------------------------------------------------------
# JobAnalysis
# ---------------------------------------------------------------------------


class TestJobAnalysis:
    def test_valid_creation(self, sample_analysis_data):
        analysis = JobAnalysis(**sample_analysis_data)
        assert analysis.fit_score == 85
        assert "PySpark" in analysis.matching_skills
        assert len(analysis.gaps) == 2
        assert len(analysis.keywords) == 7
        assert isinstance(analysis.tailoring_strategy, str)

    def test_fit_score_must_be_int(self):
        with pytest.raises(ValidationError):
            JobAnalysis(
                fit_score="high",
                fit_reasoning="good",
                matching_skills=[],
                gaps=[],
                keywords=[],
                tailoring_strategy="strategy",
            )

    def test_missing_fit_score_raises(self):
        with pytest.raises(ValidationError):
            JobAnalysis(
                fit_reasoning="good",
                matching_skills=[],
                gaps=[],
                keywords=[],
                tailoring_strategy="strategy",
            )

    def test_empty_lists_valid(self):
        analysis = JobAnalysis(
            fit_score=50,
            fit_reasoning="Average match.",
            matching_skills=[],
            gaps=[],
            keywords=[],
            tailoring_strategy="Focus on transferable skills.",
        )
        assert analysis.matching_skills == []
        assert analysis.gaps == []

    def test_model_dump_roundtrip(self, sample_analysis_data):
        analysis = JobAnalysis(**sample_analysis_data)
        dumped = analysis.model_dump()
        restored = JobAnalysis(**dumped)
        assert restored == analysis


# ---------------------------------------------------------------------------
# ResumeContent
# ---------------------------------------------------------------------------


class TestResumeContent:
    def test_valid_creation(self, sample_resume_content_data):
        content = ResumeContent(**sample_resume_content_data)
        assert "Data Engineer" in content.summary
        assert len(content.experience) == 1
        assert content.experience[0]["title"] == "Data Analyst"
        assert "Python" in content.skills_section
        assert len(content.education) == 1
        assert len(content.highlighted_projects) == 1

    def test_missing_summary_raises(self):
        with pytest.raises(ValidationError):
            ResumeContent(
                experience=[],
                skills_section="Python",
                education=[],
            )

    def test_empty_highlighted_projects_default(self):
        content = ResumeContent(
            summary="A summary.",
            experience=[],
            skills_section="Python",
            education=[],
        )
        assert content.highlighted_projects == []

    def test_experience_accepts_dicts(self):
        content = ResumeContent(
            summary="Summary",
            experience=[{"title": "Eng", "company": "Co", "dates": "2024", "bullets": ["Did stuff"]}],
            skills_section="Python",
            education=[{"degree": "BS", "institution": "Uni", "year": "2020"}],
        )
        assert content.experience[0]["title"] == "Eng"


# ---------------------------------------------------------------------------
# CoverLetterContent
# ---------------------------------------------------------------------------


class TestCoverLetterContent:
    def test_valid_creation(self, sample_cover_letter_data):
        content = CoverLetterContent(**sample_cover_letter_data)
        assert content.greeting == "Dear Hiring Manager,"
        assert len(content.body_paragraphs) == 2
        assert content.sign_off == "Sincerely,"

    def test_missing_greeting_raises(self):
        with pytest.raises(ValidationError):
            CoverLetterContent(
                opening_paragraph="Hello",
                body_paragraphs=["Body"],
                closing_paragraph="Thanks",
                sign_off="Best,",
            )

    def test_missing_body_paragraphs_raises(self):
        with pytest.raises(ValidationError):
            CoverLetterContent(
                greeting="Dear Hiring Manager,",
                opening_paragraph="Excited to apply.",
                closing_paragraph="Thank you.",
                sign_off="Sincerely,",
            )

    def test_single_body_paragraph(self):
        content = CoverLetterContent(
            greeting="Dear Team,",
            opening_paragraph="Opening.",
            body_paragraphs=["Single body paragraph."],
            closing_paragraph="Closing.",
            sign_off="Best,",
        )
        assert len(content.body_paragraphs) == 1

    def test_model_dump_roundtrip(self, sample_cover_letter_data):
        content = CoverLetterContent(**sample_cover_letter_data)
        dumped = content.model_dump()
        restored = CoverLetterContent(**dumped)
        assert restored == content
