"""Tests for PostgreSQL SQLAlchemy ORM models."""

from sqlalchemy import inspect

from src.db.models import (
    Analysis,
    Answer,
    ApiUsageLog,
    Application,
    Job,
    JobSkill,
    SearchConfig,
    Task,
    Tenant,
    User,
    UserProfile,
)


def test_tenant_has_expected_columns():
    mapper = inspect(Tenant)
    columns = {c.key for c in mapper.columns}
    assert columns >= {"id", "name", "slug", "plan", "api_usage", "rate_limits", "created_at", "updated_at"}


def test_user_has_tenant_id():
    mapper = inspect(User)
    columns = {c.key for c in mapper.columns}
    assert "tenant_id" in columns
    assert "email" in columns
    assert "hashed_password" in columns
    assert "role" in columns


def test_job_has_tenant_id():
    mapper = inspect(Job)
    columns = {c.key for c in mapper.columns}
    assert "tenant_id" in columns
    assert "url" in columns
    assert "title" in columns


def test_all_tenant_tables_have_tenant_id():
    for model in [Job, Analysis, Application, JobSkill, Answer, Task, SearchConfig, ApiUsageLog, UserProfile]:
        mapper = inspect(model)
        columns = {c.key for c in mapper.columns}
        assert "tenant_id" in columns, f"{model.__tablename__} missing tenant_id"


def test_user_profile_has_resume_fields():
    mapper = inspect(UserProfile)
    columns = {c.key for c in mapper.columns}
    assert columns >= {"full_name", "contact", "summary", "experience", "education", "skills", "certifications", "projects"}
