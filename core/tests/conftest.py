"""Shared fixtures for the job-application-assistant test suite."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.db.database import init_db

DATA_DIR = Path(__file__).parent.parent.parent / "data"


@pytest.fixture()
def tmp_db(tmp_path):
    """Create a temporary SQLite database, patch DB_PATH, and initialize schema."""
    db_file = tmp_path / "test_jobs.db"
    with patch("src.db.database.DB_PATH", db_file):
        init_db()
        yield db_file


@pytest.fixture()
def sample_job_data():
    """Realistic job posting data dict (matches the shape expected by save_job)."""
    return {
        "title": "Senior Data Engineer",
        "company": "Acme Corp",
        "location": "San Francisco, CA (Remote)",
        "salary_range": "$150,000 - $200,000",
        "job_type": "full-time",
        "experience_level": "senior",
        "description": (
            "We are looking for a Senior Data Engineer to design and build "
            "scalable data pipelines using PySpark, Airflow, and AWS. You will "
            "work closely with data scientists and analysts to deliver clean, "
            "reliable datasets that power business decisions."
        ),
        "requirements": [
            "5+ years of data engineering experience",
            "Strong Python and SQL skills",
            "Experience with PySpark or similar distributed computing",
            "AWS experience (S3, Glue, Redshift)",
            "Experience with workflow orchestration (Airflow, Dagster)",
        ],
        "responsibilities": [
            "Design and maintain production data pipelines",
            "Optimize query performance on petabyte-scale datasets",
            "Collaborate with data science team on feature engineering",
            "Mentor junior engineers and conduct code reviews",
        ],
        "benefits": [
            "Competitive salary and equity",
            "Remote-first culture",
            "Unlimited PTO",
            "Health, dental, and vision insurance",
        ],
        "application_url": "https://acme.com/careers/senior-data-engineer",
        "date_posted": "2026-03-15",
    }


@pytest.fixture()
def sample_analysis_data():
    """Realistic analysis data dict (matches the shape expected by save_analysis)."""
    return {
        "fit_score": 85,
        "fit_reasoning": (
            "The candidate has strong alignment with 5+ years of data engineering, "
            "PySpark, Airflow, and AWS experience. Minor gap in petabyte-scale "
            "optimization but strong overall match."
        ),
        "matching_skills": [
            "Python",
            "PySpark",
            "Airflow",
            "AWS (S3, Redshift)",
            "SQL",
            "Data pipeline design",
            "Docker",
            "dbt",
        ],
        "gaps": [
            "Petabyte-scale query optimization",
            "Glue-specific experience",
        ],
        "keywords": [
            "data pipelines",
            "PySpark",
            "Airflow",
            "AWS",
            "ETL",
            "data engineering",
            "Redshift",
        ],
        "tailoring_strategy": (
            "Emphasize PySpark and Airflow pipeline work from Zutrax and UNF. "
            "Highlight the 250GB+ traffic data project as evidence of large-scale "
            "processing. Lead with AWS experience from Zutrax."
        ),
    }


@pytest.fixture()
def master_resume():
    """Load the real master_resume.json file."""
    resume_path = DATA_DIR / "master_resume.json"
    return json.loads(resume_path.read_text())


@pytest.fixture()
def sample_resume_content_data():
    """Realistic resume content data matching ResumeContent model."""
    return {
        "summary": (
            "Data Engineer with 8+ years building production data pipelines "
            "and ML systems. Experienced with PySpark, Airflow, and AWS."
        ),
        "experience": [
            {
                "title": "Data Analyst",
                "company": "The Law Offices of Jacob Emrani",
                "dates": "Dec 2025 - Present",
                "bullets": [
                    "Engineered data pipelines using PySpark and Airflow to process 15K+ daily records.",
                    "Architected medallion lakehouse on AWS S3 and PostgreSQL.",
                    "Deployed production ML systems and AI agents handling 500+ concurrent inquiries.",
                ],
            },
        ],
        "skills_section": "Python, PySpark, Airflow, AWS, SQL, Docker, dbt, Kafka",
        "education": [
            {
                "degree": "M.Sc. Computing & Information Sciences: Data Science",
                "institution": "University of North Florida",
                "year": "2024",
                "details": "GPA: 4.0/4.0",
            },
        ],
        "highlighted_projects": [
            {
                "name": "Production Data Pipeline",
                "description": "Built end-to-end ELT pipeline using dlt, dbt, and Dagster.",
            },
        ],
    }


@pytest.fixture()
def sample_cover_letter_data():
    """Realistic cover letter content data matching CoverLetterContent model."""
    return {
        "greeting": "Dear Hiring Manager,",
        "opening_paragraph": (
            "I am writing to express my interest in the Senior Data Engineer "
            "position at Acme Corp. With 8+ years of experience building "
            "production data systems, I am excited about the opportunity to "
            "contribute to your data infrastructure."
        ),
        "body_paragraphs": [
            (
                "In my current role, I engineer data pipelines using PySpark, "
                "Airflow, and Kafka to process 15K+ daily records. I have "
                "architected a medallion lakehouse on AWS S3 that improved "
                "operational efficiency by 40%."
            ),
            (
                "My graduate research involved processing 250GB+ of data from "
                "5 institutional sites, where I reduced processing time by 60% "
                "through optimized PySpark pipelines."
            ),
        ],
        "closing_paragraph": (
            "I would welcome the opportunity to discuss how my experience "
            "building scalable data systems aligns with Acme Corp's needs."
        ),
        "sign_off": "Sincerely,",
    }
