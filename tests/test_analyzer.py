"""Tests for job analysis in src/analyzer/job_analyzer.py."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.analyzer import job_analyzer as analyzer
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


class TestAnalyzeJob:
    @pytest.fixture()
    def sample_job(self, sample_job_data):
        return JobPosting(**sample_job_data)

    def _mock_claude_analysis(self, analysis_data):
        block = MagicMock()
        block.text = json.dumps(analysis_data)
        message = MagicMock()
        message.content = [block]
        return message

    def test_returns_valid_job_analysis(self, sample_job, sample_analysis_data, master_resume):
        mock_msg = self._mock_claude_analysis(sample_analysis_data)

        with (
            patch("src.analyzer.job_analyzer.anthropic") as mock_anthropic,
            patch.object(analyzer, "load_master_resume", return_value=master_resume),
        ):
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_msg

            result = analyzer.analyze_job(sample_job)

            assert isinstance(result, JobAnalysis)
            assert result.fit_score == 85
            assert len(result.matching_skills) > 0
            assert isinstance(result.tailoring_strategy, str)

    def test_prompt_includes_job_details(self, sample_job, sample_analysis_data, master_resume):
        mock_msg = self._mock_claude_analysis(sample_analysis_data)

        with (
            patch("src.analyzer.job_analyzer.anthropic") as mock_anthropic,
            patch.object(analyzer, "load_master_resume", return_value=master_resume),
        ):
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_msg

            analyzer.analyze_job(sample_job)

            call_args = mock_client.messages.create.call_args
            content_blocks = call_args[1]["messages"][0]["content"]
            prompt = " ".join(b["text"] for b in content_blocks)
            assert "Senior Data Engineer" in prompt
            assert "Acme Corp" in prompt
            assert "PySpark" in prompt

    def test_handles_empty_requirements(self, sample_analysis_data, master_resume):
        job = JobPosting(
            title="Engineer",
            company="Co",
            location="Remote",
            description="Build things.",
            requirements=[],
            responsibilities=[],
        )
        mock_msg = self._mock_claude_analysis(sample_analysis_data)

        with (
            patch("src.analyzer.job_analyzer.anthropic") as mock_anthropic,
            patch.object(analyzer, "load_master_resume", return_value=master_resume),
        ):
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = mock_msg

            result = analyzer.analyze_job(job)
            assert isinstance(result, JobAnalysis)

    def test_api_error_propagates(self, sample_job, master_resume):
        with (
            patch("src.analyzer.job_analyzer.anthropic") as mock_anthropic,
            patch.object(analyzer, "load_master_resume", return_value=master_resume),
        ):
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.side_effect = Exception("API timeout")

            with pytest.raises(Exception, match="API timeout"):
                analyzer.analyze_job(sample_job)

    def test_invalid_json_response_raises(self, sample_job, master_resume):
        block = MagicMock()
        block.text = "not json"
        message = MagicMock()
        message.content = [block]

        with (
            patch("src.analyzer.job_analyzer.anthropic") as mock_anthropic,
            patch.object(analyzer, "load_master_resume", return_value=master_resume),
        ):
            mock_client = MagicMock()
            mock_anthropic.Anthropic.return_value = mock_client
            mock_client.messages.create.return_value = message

            with pytest.raises(json.JSONDecodeError):
                analyzer.analyze_job(sample_job)
