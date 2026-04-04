"""Initial multi-tenant schema with RLS.

Revision ID: 001
Revises:
Create Date: 2026-04-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_TABLES = [
    "jobs", "analyses", "applications", "job_skills", "answers",
    "tasks", "search_configs", "api_usage_log", "user_profiles",
]


def upgrade() -> None:
    # --- tenants ---
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("slug", sa.Text, unique=True, nullable=False),
        sa.Column("plan", sa.Text, server_default="free"),
        sa.Column("api_usage", JSONB, server_default="{}"),
        sa.Column("rate_limits", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.Text, unique=True, nullable=False),
        sa.Column("hashed_password", sa.Text, nullable=True),
        sa.Column("role", sa.Text, server_default="member"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # --- user_profiles ---
    op.create_table(
        "user_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("full_name", sa.Text, nullable=True),
        sa.Column("contact", JSONB, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("experience", ARRAY(JSONB), server_default="{}"),
        sa.Column("education", ARRAY(JSONB), server_default="{}"),
        sa.Column("skills", ARRAY(sa.Text), server_default="{}"),
        sa.Column("certifications", ARRAY(sa.Text), server_default="{}"),
        sa.Column("projects", ARRAY(JSONB), server_default="{}"),
        sa.Column("raw_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # --- jobs ---
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("url_hash", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("company", sa.Text, nullable=False),
        sa.Column("location", sa.Text, nullable=True),
        sa.Column("salary_range", sa.Text, nullable=True),
        sa.Column("job_type", sa.Text, nullable=True),
        sa.Column("experience_level", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("requirements", JSONB, server_default="[]"),
        sa.Column("responsibilities", JSONB, server_default="[]"),
        sa.Column("benefits", JSONB, server_default="[]"),
        sa.Column("application_url", sa.Text, nullable=True),
        sa.Column("date_posted", sa.Text, nullable=True),
        sa.Column("raw_markdown", sa.Text, nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "url_hash"),
    )

    # --- analyses ---
    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", sa.Integer, sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("fit_score", sa.Integer, nullable=False),
        sa.Column("base_score", sa.Integer, nullable=True),
        sa.Column("penalties", JSONB, server_default="[]"),
        sa.Column("fit_reasoning", sa.Text, nullable=True),
        sa.Column("matching_skills", JSONB, server_default="[]"),
        sa.Column("gaps", JSONB, server_default="[]"),
        sa.Column("keywords", JSONB, server_default="[]"),
        sa.Column("tailoring_strategy", sa.Text, nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # --- applications ---
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", sa.Integer, sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("status", sa.Text, server_default="discovered"),
        sa.Column("resume_path", sa.Text, nullable=True),
        sa.Column("cover_letter_path", sa.Text, nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # --- job_skills ---
    op.create_table(
        "job_skills",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", sa.Integer, sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("skill", sa.Text, nullable=False),
        sa.Column("source", sa.Text, server_default="keyword"),
        sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "job_id", "skill", "source"),
    )
    op.create_index("idx_job_skills_skill", "job_skills", ["skill"])
    op.create_index("idx_job_skills_job_id", "job_skills", ["job_id"])

    # --- answers ---
    op.create_table(
        "answers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("question_hash", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("source", sa.Text, server_default="manual"),
        sa.Column("category", sa.Text, nullable=True),
        sa.Column("times_used", sa.Integer, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "question_hash"),
    )

    # --- tasks ---
    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("status", sa.Text, server_default="pending"),
        sa.Column("input", JSONB, nullable=True),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("progress", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # --- search_configs ---
    op.create_table(
        "search_configs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("config_type", sa.Text, nullable=False),
        sa.Column("config", JSONB, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # --- api_usage_log ---
    op.create_table(
        "api_usage_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("tokens_used", sa.Integer, server_default="0"),
        sa.Column("cost_estimate", sa.Numeric(10, 6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("idx_usage_tenant_date", "api_usage_log", ["tenant_id", "created_at"])

    # --- API role (non-superuser, subject to RLS) ---
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'jobapp_api') THEN CREATE ROLE jobapp_api WITH LOGIN PASSWORD 'jobapp_dev'; END IF; END $$")
    op.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO jobapp_api")
    op.execute("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO jobapp_api")
    op.execute("GRANT USAGE ON SCHEMA public TO jobapp_api")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO jobapp_api")
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO jobapp_api")

    # --- RLS policies ---
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (tenant_id = current_setting('app.current_tenant')::uuid)"
        )
        op.execute(
            f"CREATE POLICY tenant_insert ON {table} "
            f"FOR INSERT WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid)"
        )


def downgrade() -> None:
    for table in reversed(RLS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_table("api_usage_log")
    op.drop_table("search_configs")
    op.drop_table("tasks")
    op.drop_table("answers")
    op.drop_table("job_skills")
    op.drop_table("applications")
    op.drop_table("analyses")
    op.drop_table("jobs")
    op.drop_table("user_profiles")
    op.drop_table("users")
    op.drop_table("tenants")
