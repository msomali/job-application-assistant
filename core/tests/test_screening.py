"""Tests for the screening_answers.json data file."""

import json
from pathlib import Path

import pytest

SCREENING_PATH = Path(__file__).parent.parent.parent / "data" / "screening_answers.json"


@pytest.fixture()
def screening_answers():
    """Load screening_answers.json."""
    return json.loads(SCREENING_PATH.read_text())


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


class TestScreeningStructure:
    def test_file_exists(self):
        assert SCREENING_PATH.exists()

    def test_valid_json(self):
        data = json.loads(SCREENING_PATH.read_text())
        assert isinstance(data, dict)

    def test_has_required_sections(self, screening_answers):
        required = [
            "personal",
            "work_authorization",
            "experience",
            "education",
            "job_preferences",
            "diversity",
            "common_questions",
        ]
        for section in required:
            assert section in screening_answers, f"Missing section: {section}"

    def test_has_description(self, screening_answers):
        assert "_description" in screening_answers

    def test_has_matching_rules(self, screening_answers):
        assert "_matching_rules" in screening_answers


# ---------------------------------------------------------------------------
# Personal fields
# ---------------------------------------------------------------------------


class TestPersonalFields:
    def test_all_fields_present(self, screening_answers):
        personal = screening_answers["personal"]
        required_fields = [
            "full_name",
            "first_name",
            "last_name",
            "email",
            "phone",
            "city",
            "state",
            "zip_code",
            "country",
            "linkedin",
            "github",
        ]
        for field in required_fields:
            assert field in personal, f"Missing personal field: {field}"

    def test_all_fields_non_empty(self, screening_answers):
        personal = screening_answers["personal"]
        for key, value in personal.items():
            if key == "website":
                continue  # website can be empty
            if key == "preferred_name":
                continue  # optional
            assert value, f"Personal field '{key}' is empty"

    def test_email_format(self, screening_answers):
        email = screening_answers["personal"]["email"]
        assert "@" in email
        assert "." in email

    def test_phone_present(self, screening_answers):
        phone = screening_answers["personal"]["phone"]
        assert len(phone) >= 10

    def test_linkedin_is_url(self, screening_answers):
        linkedin = screening_answers["personal"]["linkedin"]
        assert "linkedin.com" in linkedin

    def test_github_is_url(self, screening_answers):
        github = screening_answers["personal"]["github"]
        assert "github.com" in github


# ---------------------------------------------------------------------------
# Work authorization
# ---------------------------------------------------------------------------


class TestWorkAuthorization:
    def test_authorized_to_work(self, screening_answers):
        wa = screening_answers["work_authorization"]
        assert wa["authorized_to_work_in_us"] is True

    def test_sponsorship_field_exists(self, screening_answers):
        wa = screening_answers["work_authorization"]
        assert "require_sponsorship" in wa
        assert isinstance(wa["require_sponsorship"], bool)

    def test_visa_status_non_empty(self, screening_answers):
        wa = screening_answers["work_authorization"]
        assert wa["visa_status"]
        assert isinstance(wa["visa_status"], str)

    def test_visa_type_present(self, screening_answers):
        wa = screening_answers["work_authorization"]
        assert "visa_type" in wa
        assert wa["visa_type"]

    def test_boolean_fields(self, screening_answers):
        wa = screening_answers["work_authorization"]
        assert isinstance(wa["us_citizen"], bool)
        assert isinstance(wa["permanent_resident"], bool)


# ---------------------------------------------------------------------------
# Experience years format
# ---------------------------------------------------------------------------


class TestExperienceYears:
    def test_all_years_fields_present(self, screening_answers):
        exp = screening_answers["experience"]
        assert "total_years_experience" in exp
        assert "years_python" in exp
        assert "years_sql" in exp

    def test_years_format_pattern(self, screening_answers):
        """All years fields should match the pattern N+ (e.g., '5+', '8+')."""
        exp = screening_answers["experience"]
        for key, value in exp.items():
            assert value.endswith("+"), f"Experience field '{key}' = '{value}' does not end with '+'"
            numeric_part = value.rstrip("+")
            assert numeric_part.isdigit(), (
                f"Experience field '{key}' = '{value}' does not have a numeric prefix"
            )

    def test_total_experience_reasonable(self, screening_answers):
        total = screening_answers["experience"]["total_years_experience"]
        years = int(total.rstrip("+"))
        assert years >= 1
        assert years <= 30

    def test_specific_skills_present(self, screening_answers):
        exp = screening_answers["experience"]
        important_skills = [
            "years_python",
            "years_sql",
            "years_data_engineering",
            "years_machine_learning",
            "years_cloud",
            "years_aws",
            "years_docker",
        ]
        for skill in important_skills:
            assert skill in exp, f"Missing experience field: {skill}"
            years = int(exp[skill].rstrip("+"))
            assert years >= 1, f"Experience for {skill} should be at least 1 year"


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------


class TestEducationSection:
    def test_has_required_fields(self, screening_answers):
        edu = screening_answers["education"]
        assert "highest_degree" in edu
        assert "major" in edu
        assert "university" in edu
        assert "graduation_year" in edu

    def test_degree_non_empty(self, screening_answers):
        assert screening_answers["education"]["highest_degree"]

    def test_graduation_year_valid(self, screening_answers):
        year = screening_answers["education"]["graduation_year"]
        assert year.isdigit()
        assert 2000 <= int(year) <= 2030


# ---------------------------------------------------------------------------
# Common questions
# ---------------------------------------------------------------------------


class TestCommonQuestions:
    def test_has_required_questions(self, screening_answers):
        cq = screening_answers["common_questions"]
        required = [
            "why_interested",
            "greatest_strength",
            "greatest_weakness",
            "where_see_yourself_5_years",
            "describe_challenge",
            "tell_me_about_yourself",
        ]
        for q in required:
            assert q in cq, f"Missing common question: {q}"

    def test_answers_non_empty(self, screening_answers):
        cq = screening_answers["common_questions"]
        for key, value in cq.items():
            if isinstance(value, str):
                assert len(value) >= 10, (
                    f"Common question '{key}' answer is too short: '{value}'"
                )

    def test_boolean_consent_fields(self, screening_answers):
        cq = screening_answers["common_questions"]
        assert isinstance(cq["background_check_consent"], bool)
        assert isinstance(cq["drug_test_consent"], bool)
        assert isinstance(cq["convicted_of_felony"], bool)
