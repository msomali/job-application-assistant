"""Tests for job analysis in src/analyzer/job_analyzer.py."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.analyzer import job_analyzer as analyzer
from src.llm.base import LLMResponse
from src.models import JobAnalysis, JobPosting

# ---------------------------------------------------------------------------
# load_master_resume
# ---------------------------------------------------------------------------


class TestLoadMasterResume:
    def test_loads_successfully(self):
        resume = analyzer.load_master_resume()
        assert isinstance(resume, dict)
        assert "name" in resume
        assert "experience" in resume
        assert "skills" in resume
        assert "education" in resume

    def test_contains_required_sections(self):
        resume = analyzer.load_master_resume()
        assert isinstance(resume["experience"], list)
        assert len(resume["experience"]) > 0
        assert isinstance(resume["skills"], list)
        assert len(resume["skills"]) > 0
        assert isinstance(resume["education"], list)

    def test_missing_file_raises(self, tmp_path):
        fake_path = tmp_path / "nonexistent.json"
        with patch.object(analyzer, "MASTER_RESUME_PATH", fake_path):
            with pytest.raises(FileNotFoundError, match="Master resume not found"):
                analyzer.load_master_resume()


# ---------------------------------------------------------------------------
# analyze_job
# ---------------------------------------------------------------------------


def _mock_router(response_data):
    """Create a mock router that returns an LLMResponse with the given JSON data."""
    mock_router = MagicMock()
    mock_router.generate_with_cache.return_value = LLMResponse(
        text=json.dumps(response_data),
        provider="anthropic",
        model="claude-sonnet-4-20250514",
    )
    return mock_router


class TestAnalyzeJob:
    @pytest.fixture()
    def sample_job(self, sample_job_data):
        return JobPosting(**sample_job_data)

    def test_returns_valid_job_analysis(self, sample_job, sample_analysis_data, master_resume):
        mock_r = _mock_router(sample_analysis_data)

        with (
            patch("src.analyzer.job_analyzer.get_router", return_value=mock_r),
            patch.object(analyzer, "load_master_resume", return_value=master_resume),
        ):
            result = analyzer.analyze_job(sample_job)

            assert isinstance(result, JobAnalysis)
            assert result.fit_score == 85
            assert len(result.matching_skills) > 0
            assert isinstance(result.tailoring_strategy, str)

    def test_prompt_includes_job_details(self, sample_job, sample_analysis_data, master_resume):
        mock_r = _mock_router(sample_analysis_data)

        with (
            patch("src.analyzer.job_analyzer.get_router", return_value=mock_r),
            patch.object(analyzer, "load_master_resume", return_value=master_resume),
        ):
            analyzer.analyze_job(sample_job)

            call_kwargs = mock_r.generate_with_cache.call_args[1]
            all_content = call_kwargs["cached_content"] + " " + call_kwargs["variable_content"]
            assert "Senior Data Engineer" in all_content
            assert "Acme Corp" in all_content
            assert "PySpark" in all_content

    def test_handles_empty_requirements(self, sample_analysis_data, master_resume):
        job = JobPosting(
            title="Engineer",
            company="Co",
            location="Remote",
            description="Build things.",
            requirements=[],
            responsibilities=[],
        )
        mock_r = _mock_router(sample_analysis_data)

        with (
            patch("src.analyzer.job_analyzer.get_router", return_value=mock_r),
            patch.object(analyzer, "load_master_resume", return_value=master_resume),
        ):
            result = analyzer.analyze_job(job)
            assert isinstance(result, JobAnalysis)

    def test_api_error_propagates(self, sample_job, master_resume):
        mock_r = MagicMock()
        mock_r.generate_with_cache.side_effect = Exception("API timeout")

        with (
            patch("src.analyzer.job_analyzer.get_router", return_value=mock_r),
            patch.object(analyzer, "load_master_resume", return_value=master_resume),
        ):
            with pytest.raises(Exception, match="API timeout"):
                analyzer.analyze_job(sample_job)

    def test_invalid_json_response_raises(self, sample_job, master_resume):
        mock_r = MagicMock()
        mock_r.generate_with_cache.return_value = LLMResponse(
            text="not json",
            provider="anthropic",
            model="test",
        )

        with (
            patch("src.analyzer.job_analyzer.get_router", return_value=mock_r),
            patch.object(analyzer, "load_master_resume", return_value=master_resume),
        ):
            with pytest.raises(ValueError, match="not valid JSON"):
                analyzer.analyze_job(sample_job)
