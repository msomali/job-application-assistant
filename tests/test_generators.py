"""Tests for resume and cover letter generators."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.generator import cover_letter_generator as cl_gen
from src.generator import resume_generator as resume_gen
from src.models import (
    CoverLetterContent,
    JobAnalysis,
    JobPosting,
    ResumeContent,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_job(sample_job_data):
    return JobPosting(**sample_job_data)


@pytest.fixture()
def sample_analysis(sample_analysis_data):
    return JobAnalysis(**sample_analysis_data)


# ---------------------------------------------------------------------------
# LaTeX escaping — resume_generator
# ---------------------------------------------------------------------------


class TestResumeLatexEscaping:
    def test_ampersand(self):
        assert resume_gen._escape_latex("A & B") == r"A \& B"

    def test_percent(self):
        assert resume_gen._escape_latex("100%") == r"100\%"

    def test_dollar(self):
        assert resume_gen._escape_latex("$100") == r"\$100"

    def test_hash(self):
        assert resume_gen._escape_latex("#1") == r"\#1"

    def test_underscore(self):
        assert resume_gen._escape_latex("data_engineer") == r"data\_engineer"

    def test_braces(self):
        assert resume_gen._escape_latex("{test}") == r"\{test\}"

    def test_tilde(self):
        assert resume_gen._escape_latex("~approx") == r"\textasciitilde{}approx"

    def test_caret(self):
        assert resume_gen._escape_latex("x^2") == r"x\textasciicircum{}2"

    def test_multiple_specials(self):
        result = resume_gen._escape_latex("A & B at $100 for #1 team_work")
        assert r"\&" in result
        assert r"\$" in result
        assert r"\#" in result
        assert r"\_" in result

    def test_no_specials_unchanged(self):
        text = "Regular text without special characters"
        assert resume_gen._escape_latex(text) == text


# ---------------------------------------------------------------------------
# LaTeX escaping — cover_letter_generator
# ---------------------------------------------------------------------------


class TestCoverLetterLatexEscaping:
    def test_ampersand(self):
        assert cl_gen._escape_latex("R & D") == r"R \& D"

    def test_all_specials_consistent_with_resume(self):
        text = "A & B % C $ D # E _ F { G } H ~ I ^ J"
        assert cl_gen._escape_latex(text) == resume_gen._escape_latex(text)


# ---------------------------------------------------------------------------
# generate_resume_content
# ---------------------------------------------------------------------------


class TestGenerateResumeContent:
    def test_returns_resume_content(
        self, sample_job, sample_analysis, master_resume, sample_resume_content_data
    ):
        block = MagicMock()
        block.text = json.dumps(sample_resume_content_data)
        message = MagicMock()
        message.content = [block]

        with patch("src.generator.resume_generator.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = message

            result = resume_gen.generate_resume_content(
                sample_job, sample_analysis, master_resume
            )

            assert isinstance(result, ResumeContent)
            assert "Data Engineer" in result.summary
            assert len(result.experience) >= 1
            assert len(result.education) >= 1

    def test_prompt_includes_job_title(
        self, sample_job, sample_analysis, master_resume, sample_resume_content_data
    ):
        block = MagicMock()
        block.text = json.dumps(sample_resume_content_data)
        message = MagicMock()
        message.content = [block]

        with patch("src.generator.resume_generator.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = message

            resume_gen.generate_resume_content(sample_job, sample_analysis, master_resume)

            call_args = mock_client.messages.create.call_args
            content_blocks = call_args[1]["messages"][0]["content"]
            prompt = " ".join(b["text"] for b in content_blocks)
            assert "Senior Data Engineer" in prompt
            assert "Acme Corp" in prompt

    def test_prompt_includes_keywords(
        self, sample_job, sample_analysis, master_resume, sample_resume_content_data
    ):
        block = MagicMock()
        block.text = json.dumps(sample_resume_content_data)
        message = MagicMock()
        message.content = [block]

        with patch("src.generator.resume_generator.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = message

            resume_gen.generate_resume_content(sample_job, sample_analysis, master_resume)

            call_args = mock_client.messages.create.call_args
            content_blocks = call_args[1]["messages"][0]["content"]
            prompt = " ".join(b["text"] for b in content_blocks)
            assert "PySpark" in prompt
            assert "Airflow" in prompt

    def test_api_error_propagates(self, sample_job, sample_analysis, master_resume):
        with patch("src.generator.resume_generator.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.side_effect = Exception("Rate limited")

            with pytest.raises(Exception, match="Rate limited"):
                resume_gen.generate_resume_content(
                    sample_job, sample_analysis, master_resume
                )


# ---------------------------------------------------------------------------
# generate_cover_letter_content
# ---------------------------------------------------------------------------


class TestGenerateCoverLetterContent:
    def test_returns_cover_letter_content(
        self, sample_job, sample_analysis, master_resume, sample_cover_letter_data
    ):
        block = MagicMock()
        block.text = json.dumps(sample_cover_letter_data)
        message = MagicMock()
        message.content = [block]

        with patch("src.generator.cover_letter_generator.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = message

            result = cl_gen.generate_cover_letter_content(
                sample_job, sample_analysis, master_resume
            )

            assert isinstance(result, CoverLetterContent)
            assert result.greeting == "Dear Hiring Manager,"
            assert len(result.body_paragraphs) == 2
            assert result.sign_off == "Sincerely,"

    def test_prompt_includes_matching_skills(
        self, sample_job, sample_analysis, master_resume, sample_cover_letter_data
    ):
        block = MagicMock()
        block.text = json.dumps(sample_cover_letter_data)
        message = MagicMock()
        message.content = [block]

        with patch("src.generator.cover_letter_generator.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = message

            cl_gen.generate_cover_letter_content(
                sample_job, sample_analysis, master_resume
            )

            call_args = mock_client.messages.create.call_args
            content_blocks = call_args[1]["messages"][0]["content"]
            prompt = " ".join(b["text"] for b in content_blocks)
            assert "Python" in prompt
            assert "PySpark" in prompt

    def test_api_error_propagates(self, sample_job, sample_analysis, master_resume):
        with patch("src.generator.cover_letter_generator.anthropic") as mock_anthropic:
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.side_effect = Exception("Service unavailable")

            with pytest.raises(Exception, match="Service unavailable"):
                cl_gen.generate_cover_letter_content(
                    sample_job, sample_analysis, master_resume
                )


# ---------------------------------------------------------------------------
# _build_experience_latex
# ---------------------------------------------------------------------------


class TestBuildExperienceLatex:
    def test_generates_latex_sections(self):
        experience = [
            {
                "title": "Data Engineer",
                "company": "Acme Corp",
                "dates": "2023 - Present",
                "bullets": ["Built data pipelines", "Optimized queries"],
            }
        ]
        latex = resume_gen._build_experience_latex(experience)
        assert r"\cvsection" in latex
        assert "Data Engineer" in latex
        assert "Acme Corp" in latex
        assert r"\item" in latex
        assert "Built data pipelines" in latex

    def test_escapes_special_chars_in_bullets(self):
        experience = [
            {
                "title": "Engineer",
                "company": "R&D Co",
                "dates": "2023",
                "bullets": ["Improved pipeline speed by 50%"],
            }
        ]
        latex = resume_gen._build_experience_latex(experience)
        assert r"R\&D Co" in latex
        assert r"50\%" in latex

    def test_empty_experience(self):
        latex = resume_gen._build_experience_latex([])
        assert latex == ""


# ---------------------------------------------------------------------------
# _build_education_latex
# ---------------------------------------------------------------------------


class TestBuildEducationLatex:
    def test_generates_latex_sections(self):
        education = [
            {
                "degree": "M.Sc. Data Science",
                "institution": "UNF",
                "year": "2024",
                "details": "GPA: 4.0",
            }
        ]
        latex = resume_gen._build_education_latex(education)
        assert r"\cvsection" in latex
        assert "M.Sc. Data Science" in latex
        assert "UNF" in latex
        assert "GPA: 4.0" in latex

    def test_no_details(self):
        education = [
            {
                "degree": "B.Sc. CS",
                "institution": "MIT",
                "year": "2020",
            }
        ]
        latex = resume_gen._build_education_latex(education)
        assert "MIT" in latex
        assert " -- " not in latex


# ---------------------------------------------------------------------------
# _build_projects_latex
# ---------------------------------------------------------------------------


class TestBuildProjectsLatex:
    def test_generates_project_section(self):
        projects = [
            {
                "name": "ML Pipeline",
                "description": "Built an end-to-end ML pipeline.",
            }
        ]
        latex = resume_gen._build_projects_latex(projects)
        assert r"\section*{Projects}" in latex
        assert r"\textbf{ML Pipeline}" in latex

    def test_empty_projects_returns_empty(self):
        assert resume_gen._build_projects_latex([]) == ""
