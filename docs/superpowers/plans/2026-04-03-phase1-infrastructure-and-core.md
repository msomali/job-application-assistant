# Phase 1: Infrastructure, Database & Core Refactor

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up Docker infrastructure (PostgreSQL, Redis, MinIO), create Alembic migrations for the multi-tenant schema with RLS, and refactor the existing `src/` into an installable `core/` package that both CLI and API can import.

**Architecture:** Modular monorepo with `core/` (existing logic, zero web deps), `api/` (FastAPI, created in Phase 2), and `web/` (React/Vite, created in Phase 3). This phase creates `core/` and the infrastructure layer. The CLI continues to work via `core/`.

**Tech Stack:** PostgreSQL 16, Redis 7, MinIO, Alembic, SQLAlchemy (for migrations and async DB access), Docker Compose, Python 3.11

**Phasing note:** This is Phase 1 of 4. Subsequent phases:
- Phase 2: FastAPI API layer (auth, routes, middleware, Celery workers, SSE)
- Phase 3: React/Vite frontend (pages, components, stores)
- Phase 4: Integration, E2E testing, production deployment

---

## File Structure

```
job-application-assistant/
├── core/
│   ├── pyproject.toml              # installable package `job-core`
│   ├── src/                        # moved from top-level src/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── config.py
│   │   ├── utils.py
│   │   ├── logging_config.py
│   │   ├── batch.py
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── database.py         # existing SQLite (kept for CLI backward compat)
│   │   │   ├── pg.py               # new: async PostgreSQL connection + RLS helper
│   │   │   └── models.py           # new: SQLAlchemy ORM models for all tables
│   │   ├── scraper/
│   │   ├── analyzer/
│   │   ├── generator/
│   │   ├── templates/
│   │   ├── llm/
│   │   ├── privacy/
│   │   └── agent/
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py                 # moved from src/main.py
│   └── tests/                      # moved from top-level tests/
│       ├── conftest.py
│       └── ... (existing test files)
├── api/                            # (Phase 2 — empty placeholder)
│   └── .gitkeep
├── web/                            # (Phase 3 — empty placeholder)
│   └── .gitkeep
├── alembic/                        # Alembic migrations (shared, not inside api/)
│   ├── alembic.ini
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
├── docker-compose.yml
├── docker-compose.dev.yml          # dev overrides (hot reload, port exposure)
├── .env.example                    # updated with PG/Redis/MinIO vars
├── Makefile
└── pyproject.toml                  # workspace root (updated)
```

---

### Task 1: Docker Compose for Infrastructure Services

**Files:**
- Create: `docker-compose.yml`
- Create: `docker-compose.dev.yml`
- Update: `.env.example`

- [ ] **Step 1: Create docker-compose.yml**

```yaml
# docker-compose.yml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-jobapp}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-jobapp_dev}
      POSTGRES_DB: ${POSTGRES_DB:-jobapp}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-jobapp}"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
    ports:
      - "${MINIO_API_PORT:-9000}:9000"
      - "${MINIO_CONSOLE_PORT:-9001}:9001"
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      timeout: 3s
      retries: 5

  minio-init:
    image: minio/mc:latest
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
      mc alias set local http://minio:9000 $${MINIO_ROOT_USER:-minioadmin} $${MINIO_ROOT_PASSWORD:-minioadmin};
      mc mb --ignore-existing local/jobapp-documents;
      mc mb --ignore-existing local/jobapp-screenshots;
      exit 0;
      "

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

- [ ] **Step 2: Create docker-compose.dev.yml**

```yaml
# docker-compose.dev.yml
# Dev overrides — use with: docker compose -f docker-compose.yml -f docker-compose.dev.yml up
version: "3.9"

services:
  postgres:
    ports:
      - "5432:5432"

  redis:
    ports:
      - "6379:6379"

  minio:
    ports:
      - "9000:9000"
      - "9001:9001"
```

- [ ] **Step 3: Update .env.example with new variables**

Add these lines to the existing `.env.example`:

```bash
# PostgreSQL
POSTGRES_USER=jobapp
POSTGRES_PASSWORD=jobapp_dev
POSTGRES_DB=jobapp
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}

# Redis
REDIS_URL=redis://localhost:6379/0

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_DOCUMENTS_BUCKET=jobapp-documents
MINIO_SCREENSHOTS_BUCKET=jobapp-screenshots
MINIO_USE_SSL=false
```

- [ ] **Step 4: Start services and verify**

Run: `docker compose up -d`

Expected: All 3 services healthy. Verify:
```bash
docker compose ps                           # all services "healthy"
docker compose exec postgres pg_isready     # /var/run/postgresql:5432 - accepting connections
docker compose exec redis redis-cli ping    # PONG
curl -s http://localhost:9000/minio/health/live  # HTTP 200
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml docker-compose.dev.yml
git commit -m "feat: add Docker Compose for PostgreSQL, Redis, and MinIO"
```

---

### Task 2: Create Makefile for Common Operations

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create Makefile**

```makefile
# Makefile — common development commands

.PHONY: infra infra-down migrate test lint

# Start infrastructure services
infra:
	docker compose up -d

# Stop infrastructure services
infra-down:
	docker compose down

# Run Alembic migrations
migrate:
	alembic upgrade head

# Run core tests
test:
	cd core && pytest -v --tb=short

# Lint core
lint:
	ruff check core/src/ core/tests/

# Generate new migration
migration:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

# Reset database (destructive)
db-reset:
	docker compose exec postgres psql -U jobapp -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	alembic upgrade head
```

- [ ] **Step 2: Commit**

```bash
git add Makefile
git commit -m "feat: add Makefile for infrastructure and dev commands"
```

---

### Task 3: Refactor src/ into core/ Package

This is the most critical task — moves existing code into `core/` without breaking imports. The CLI still works after this.

**Files:**
- Move: `src/` → `core/src/`
- Move: `src/main.py` → `core/cli/main.py`
- Move: `tests/` → `core/tests/`
- Create: `core/pyproject.toml`
- Create: `core/cli/__init__.py`
- Modify: `pyproject.toml` (root — update to point to core)

- [ ] **Step 1: Create core directory structure**

```bash
mkdir -p core/cli
```

- [ ] **Step 2: Move src/ into core/src/**

```bash
git mv src/ core/src/
```

- [ ] **Step 3: Move main.py to cli/**

```bash
git mv core/src/main.py core/cli/main.py
touch core/cli/__init__.py
```

- [ ] **Step 4: Move tests/ into core/tests/**

```bash
git mv tests/ core/tests/
```

- [ ] **Step 5: Create core/pyproject.toml**

```toml
[project]
name = "job-core"
version = "0.1.0"
description = "Core library for Job Application Assistant — scraper, analyzer, generator, LLM routing"
requires-python = ">=3.11"
dependencies = [
    "firecrawl-py==4.19.0",
    "anthropic==0.86.0",
    "pydantic==2.12.5",
    "sqlite-utils==3.39",
    "click==8.3.1",
    "claude-agent-sdk==0.1.50",
    "python-telegram-bot==22.7",
    "playwright==1.58.0",
    "python-dotenv==1.2.2",
    "pyyaml>=6.0",
    "Pillow>=10.0",
    "google-genai>=1.0",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "boto3>=1.35",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.4",
    "mypy>=1.10",
    "pre-commit>=4.0",
]

[project.scripts]
job = "cli.main:cli"

[tool.setuptools.packages.find]
where = ["."]
include = ["src*", "cli*"]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "S", "B", "UP"]
ignore = [
    "S608",
    "S603",
    "S110",
    "S112",
    "E501",
    "E402",
]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101"]
```

- [ ] **Step 6: Update imports in core/cli/main.py**

The CLI file imports from `src.*` — these still work because `core/src/` is on the Python path. Verify the entry point path changed in `core/pyproject.toml` to `cli.main:cli`.

No code changes needed in main.py itself — the imports (`from src.analyzer.job_analyzer import ...`) still resolve because `core/` is the package root and `src/` is a subdirectory with `__init__.py`.

- [ ] **Step 7: Update root pyproject.toml**

Replace the root `pyproject.toml` content to become a workspace coordinator:

```toml
[project]
name = "job-application-assistant"
version = "0.1.0"
description = "Automated job application pipeline — monorepo workspace"
requires-python = ">=3.11"
dependencies = [
    "job-core @ file:///./core",
]

[project.scripts]
job = "cli.main:cli"

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 8: Update .env loading path in cli/main.py**

The dotenv path in `main.py` line 10 uses `Path(__file__).parent.parent / ".env"`. After the move, `__file__` is `core/cli/main.py`, so `parent.parent` is `core/`, but `.env` is at the repo root. Fix:

In `core/cli/main.py`, change:
```python
load_dotenv(Path(__file__).parent.parent / ".env")
```
to:
```python
load_dotenv(Path(__file__).parent.parent.parent / ".env")
```

- [ ] **Step 9: Update config.py path**

In `core/src/config.py`, the `CONFIG_PATH` is `Path(__file__).parent.parent / "data" / "config.yaml"`. After the move, `__file__` is `core/src/config.py`, so `parent.parent` is `core/`, but `data/` is at repo root. Fix:

In `core/src/config.py`, change:
```python
CONFIG_PATH = Path(__file__).parent.parent / "data" / "config.yaml"
```
to:
```python
CONFIG_PATH = Path(__file__).parent.parent.parent / "data" / "config.yaml"
```

- [ ] **Step 10: Update database.py path**

In `core/src/db/database.py`, `DB_PATH` is `Path(__file__).parent.parent.parent / "data" / "jobs.db"`. After the move, `__file__` is `core/src/db/database.py`, so we need one more `.parent`. Fix:

In `core/src/db/database.py`, change:
```python
DB_PATH = Path(__file__).parent.parent.parent / "data" / "jobs.db"
```
to:
```python
DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "jobs.db"
```

- [ ] **Step 11: Update OUTPUT_DIR in main.py and agent.py**

In `core/cli/main.py`, fix the OUTPUT_DIR path (add one more `.parent`):
```python
OUTPUT_DIR = Path(__file__).parent.parent.parent / (cfg("generation", "output_dir") or "output")
```

In `core/src/agent/agent.py`, fix:
```python
OUTPUT_DIR = Path(__file__).parent.parent.parent.parent / "output"
```

In `core/src/agent/telegram_bot.py`, fix:
```python
OUTPUT_DIR = Path(__file__).parent.parent.parent.parent / "output"
```

- [ ] **Step 12: Update conftest.py path**

In `core/tests/conftest.py`, fix:
```python
DATA_DIR = Path(__file__).parent.parent.parent / "data"
```

- [ ] **Step 13: Install and verify CLI works**

```bash
cd core && pip install -e ".[dev]" && cd ..
job --help
```

Expected: CLI help output showing all commands.

- [ ] **Step 14: Run existing tests**

```bash
cd core && pytest -v --tb=short
```

Expected: All existing tests pass (mocked external APIs, tmp_db fixture).

- [ ] **Step 15: Commit**

```bash
git add -A
git commit -m "refactor: move src/ to core/src/, cli to core/cli/, tests to core/tests/

Restructures the repo into a modular monorepo. The core/ package
is installable as job-core. CLI still works via 'job' command.
All existing tests pass."
```

---

### Task 4: SQLAlchemy ORM Models for PostgreSQL

**Files:**
- Create: `core/src/db/models.py`
- Create: `core/tests/test_pg_models.py`

- [ ] **Step 1: Write test for ORM model imports and field presence**

Create `core/tests/test_pg_models.py`:

```python
"""Tests for PostgreSQL SQLAlchemy ORM models."""

from uuid import UUID

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
    """Every table that needs RLS must have a tenant_id column."""
    for model in [Job, Analysis, Application, JobSkill, Answer, Task, SearchConfig, ApiUsageLog, UserProfile]:
        mapper = inspect(model)
        columns = {c.key for c in mapper.columns}
        assert "tenant_id" in columns, f"{model.__tablename__} missing tenant_id"


def test_user_profile_has_resume_fields():
    mapper = inspect(UserProfile)
    columns = {c.key for c in mapper.columns}
    assert columns >= {"full_name", "contact", "summary", "experience", "education", "skills", "certifications", "projects"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && pytest tests/test_pg_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.db.models'`

- [ ] **Step 3: Create ORM models**

Create `core/src/db/models.py`:

```python
"""SQLAlchemy ORM models for the PostgreSQL multi-tenant schema."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(Text, default="free")
    api_usage: Mapped[dict] = mapped_column(JSONB, default=dict)
    rate_limits: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="tenant")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(Text, default="member")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    tenant: Mapped["Tenant"] = relationship(back_populates="users")
    profile: Mapped["UserProfile | None"] = relationship(back_populates="user")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience: Mapped[list | None] = mapped_column(ARRAY(JSONB), default=list)
    education: Mapped[list | None] = mapped_column(ARRAY(JSONB), default=list)
    skills: Mapped[list | None] = mapped_column(ARRAY(Text), default=list)
    certifications: Mapped[list | None] = mapped_column(ARRAY(Text), default=list)
    projects: Mapped[list | None] = mapped_column(ARRAY(JSONB), default=list)
    raw_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    user: Mapped["User"] = relationship(back_populates="profile")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("tenant_id", "url_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_hash: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_range: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements: Mapped[list] = mapped_column(JSONB, default=list)
    responsibilities: Mapped[list] = mapped_column(JSONB, default=list)
    benefits: Mapped[list] = mapped_column(JSONB, default=list)
    application_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_posted: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    analyses: Mapped[list["Analysis"]] = relationship(back_populates="job")
    skills: Mapped[list["JobSkill"]] = relationship(back_populates="job")


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False)
    fit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    base_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    penalties: Mapped[list] = mapped_column(JSONB, default=list)
    fit_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    matching_skills: Mapped[list] = mapped_column(JSONB, default=list)
    gaps: Mapped[list] = mapped_column(JSONB, default=list)
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    tailoring_strategy: Mapped[str | None] = mapped_column(Text, nullable=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    job: Mapped["Job"] = relationship(back_populates="analyses")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, default="discovered")
    resume_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_letter_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class JobSkill(Base):
    __tablename__ = "job_skills"
    __table_args__ = (UniqueConstraint("tenant_id", "job_id", "skill", "source"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), nullable=False)
    skill: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, default="keyword")
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    job: Mapped["Job"] = relationship(back_populates="skills")


class Answer(Base):
    __tablename__ = "answers"
    __table_args__ = (UniqueConstraint("tenant_id", "question_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    question_hash: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, default="manual")
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    times_used: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending")
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class SearchConfig(Base):
    __tablename__ = "search_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    config_type: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ApiUsageLog(Base):
    __tablename__ = "api_usage_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    cost_estimate: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd core && pytest tests/test_pg_models.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/db/models.py core/tests/test_pg_models.py
git commit -m "feat: add SQLAlchemy ORM models for multi-tenant PostgreSQL schema"
```

---

### Task 5: Async PostgreSQL Connection Module

**Files:**
- Create: `core/src/db/pg.py`
- Create: `core/tests/test_pg_connection.py`

- [ ] **Step 1: Write test for connection factory and RLS helper**

Create `core/tests/test_pg_connection.py`:

```python
"""Tests for PostgreSQL async connection module."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from src.db.pg import get_database_url, set_tenant_context


def test_get_database_url_from_env():
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/testdb"}):
        url = get_database_url()
        assert "postgresql+asyncpg" in url
        assert "testdb" in url


def test_get_database_url_from_components():
    env = {
        "POSTGRES_USER": "myuser",
        "POSTGRES_PASSWORD": "mypass",
        "POSTGRES_HOST": "dbhost",
        "POSTGRES_PORT": "5433",
        "POSTGRES_DB": "mydb",
    }
    with patch.dict(os.environ, env, clear=False):
        # Remove DATABASE_URL if set
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DATABASE_URL", None)
            url = get_database_url()
            assert url == "postgresql+asyncpg://myuser:mypass@dbhost:5433/mydb"


@pytest.mark.asyncio
async def test_set_tenant_context():
    mock_session = AsyncMock()
    tenant_id = "550e8400-e29b-41d4-a716-446655440000"
    await set_tenant_context(mock_session, tenant_id)
    mock_session.execute.assert_called_once()
    call_args = str(mock_session.execute.call_args)
    assert "app.current_tenant" in call_args
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && pytest tests/test_pg_connection.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.db.pg'`

- [ ] **Step 3: Create pg.py**

Create `core/src/db/pg.py`:

```python
"""Async PostgreSQL connection management with RLS tenant context."""

import logging
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None


def get_database_url() -> str:
    """Build database URL from DATABASE_URL env var or individual components."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    user = os.environ.get("POSTGRES_USER", "jobapp")
    password = os.environ.get("POSTGRES_PASSWORD", "jobapp_dev")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "jobapp")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


def get_engine():
    """Get or create the async SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_database_url(),
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """Set the RLS tenant context for the current database session.

    Must be called at the start of every request before any tenant-scoped query.
    """
    await session.execute(text(f"SET app.current_tenant = '{tenant_id}'"))


async def reset_engine() -> None:
    """Dispose the current engine. Used in tests and graceful shutdown."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
    _engine = None
    _session_factory = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd core && pytest tests/test_pg_connection.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/db/pg.py core/tests/test_pg_connection.py
git commit -m "feat: add async PostgreSQL connection module with RLS tenant context"
```

---

### Task 6: Alembic Setup and Initial Migration

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/001_initial_schema.py`

- [ ] **Step 1: Install Alembic**

```bash
pip install alembic
```

- [ ] **Step 2: Create alembic.ini at repo root**

```ini
# alembic.ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql://jobapp:jobapp_dev@localhost:5432/jobapp

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3: Create alembic/env.py**

```python
"""Alembic environment configuration — imports ORM models for autogenerate."""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add core/ to path so we can import ORM models
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))

from src.db.models import Base  # noqa: E402

config = context.config

# Override sqlalchemy.url from environment if available
db_url = os.environ.get("DATABASE_URL", "").replace("+asyncpg", "")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL without a live connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects to the database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Create alembic/script.py.mako**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 5: Create the initial migration**

Create `alembic/versions/001_initial_schema.py`:

```python
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

# Tables that get RLS policies
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

    # --- RLS policies ---
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
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
```

- [ ] **Step 6: Run migration against local PostgreSQL**

Ensure Docker services are running:
```bash
docker compose up -d
```

Run migration:
```bash
alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade  -> 001, Initial multi-tenant schema with RLS.`

- [ ] **Step 7: Verify schema in PostgreSQL**

```bash
docker compose exec postgres psql -U jobapp -c "\dt"
```

Expected: 11 tables listed (tenants, users, user_profiles, jobs, analyses, applications, job_skills, answers, tasks, search_configs, api_usage_log, plus alembic_version).

- [ ] **Step 8: Verify RLS is enabled**

```bash
docker compose exec postgres psql -U jobapp -c "SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public' AND rowsecurity = true;"
```

Expected: 9 tables with `rowsecurity = true`.

- [ ] **Step 9: Commit**

```bash
git add alembic.ini alembic/
git commit -m "feat: add Alembic migrations for multi-tenant schema with RLS policies"
```

---

### Task 7: MinIO Storage Helper

**Files:**
- Create: `core/src/storage.py`
- Create: `core/tests/test_storage.py`

- [ ] **Step 1: Write tests for MinIO storage helper**

Create `core/tests/test_storage.py`:

```python
"""Tests for MinIO/S3 storage helper."""

from unittest.mock import MagicMock, patch

import pytest

from src.storage import StorageClient


@pytest.fixture
def mock_boto3():
    with patch("src.storage.boto3") as mock:
        mock_client = MagicMock()
        mock.client.return_value = mock_client
        yield mock_client


def test_upload_file(mock_boto3, tmp_path):
    client = StorageClient.__new__(StorageClient)
    client._client = mock_boto3
    client._documents_bucket = "jobapp-documents"
    client._screenshots_bucket = "jobapp-screenshots"

    test_file = tmp_path / "resume.pdf"
    test_file.write_bytes(b"%PDF-fake-content")

    key = client.upload_document("tenant-123", "resume.pdf", str(test_file))

    mock_boto3.upload_file.assert_called_once_with(
        str(test_file), "jobapp-documents", "tenant-123/resume.pdf"
    )
    assert key == "tenant-123/resume.pdf"


def test_get_presigned_url(mock_boto3):
    client = StorageClient.__new__(StorageClient)
    client._client = mock_boto3
    client._documents_bucket = "jobapp-documents"
    client._screenshots_bucket = "jobapp-screenshots"
    mock_boto3.generate_presigned_url.return_value = "https://minio:9000/signed-url"

    url = client.get_document_url("tenant-123/resume.pdf")

    mock_boto3.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "jobapp-documents", "Key": "tenant-123/resume.pdf"},
        ExpiresIn=3600,
    )
    assert url == "https://minio:9000/signed-url"


def test_delete_document(mock_boto3):
    client = StorageClient.__new__(StorageClient)
    client._client = mock_boto3
    client._documents_bucket = "jobapp-documents"
    client._screenshots_bucket = "jobapp-screenshots"

    client.delete_document("tenant-123/resume.pdf")

    mock_boto3.delete_object.assert_called_once_with(
        Bucket="jobapp-documents", Key="tenant-123/resume.pdf"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd core && pytest tests/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.storage'`

- [ ] **Step 3: Create storage.py**

Create `core/src/storage.py`:

```python
"""MinIO/S3-compatible object storage client for PDFs and screenshots."""

import logging
import os

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


class StorageClient:
    """S3-compatible storage client. Works with MinIO locally, AWS S3 in production."""

    def __init__(self) -> None:
        endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
        use_ssl = os.environ.get("MINIO_USE_SSL", "false").lower() == "true"
        scheme = "https" if use_ssl else "http"

        self._client = boto3.client(
            "s3",
            endpoint_url=f"{scheme}://{endpoint}",
            aws_access_key_id=os.environ.get("MINIO_ROOT_USER", "minioadmin"),
            aws_secret_access_key=os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin"),
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self._documents_bucket = os.environ.get("MINIO_DOCUMENTS_BUCKET", "jobapp-documents")
        self._screenshots_bucket = os.environ.get("MINIO_SCREENSHOTS_BUCKET", "jobapp-screenshots")

    def upload_document(self, tenant_id: str, filename: str, local_path: str) -> str:
        """Upload a document (resume/cover letter PDF) and return the object key."""
        key = f"{tenant_id}/{filename}"
        self._client.upload_file(local_path, self._documents_bucket, key)
        logger.info("Uploaded document: %s/%s", self._documents_bucket, key)
        return key

    def upload_screenshot(self, tenant_id: str, filename: str, local_path: str) -> str:
        """Upload a screenshot and return the object key."""
        key = f"{tenant_id}/{filename}"
        self._client.upload_file(local_path, self._screenshots_bucket, key)
        return key

    def get_document_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a pre-signed URL for downloading a document."""
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._documents_bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def get_screenshot_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a pre-signed URL for viewing a screenshot."""
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._screenshots_bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete_document(self, key: str) -> None:
        """Delete a document from storage."""
        self._client.delete_object(Bucket=self._documents_bucket, Key=key)
        logger.info("Deleted document: %s/%s", self._documents_bucket, key)

    def delete_screenshot(self, key: str) -> None:
        """Delete a screenshot from storage."""
        self._client.delete_object(Bucket=self._screenshots_bucket, Key=key)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd core && pytest tests/test_storage.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/storage.py core/tests/test_storage.py
git commit -m "feat: add MinIO/S3 storage client for tenant-scoped document management"
```

---

### Task 8: RLS Integration Test

**Files:**
- Create: `core/tests/test_rls_integration.py`

This test requires a running PostgreSQL instance. It verifies that RLS actually prevents cross-tenant data access.

- [ ] **Step 1: Write RLS integration test**

Create `core/tests/test_rls_integration.py`:

```python
"""Integration test: verify PostgreSQL RLS prevents cross-tenant access.

Requires running PostgreSQL (docker compose up -d).
Skip with: pytest -m "not integration"
"""

import os
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, text

# Use sync driver for simpler test setup
SYNC_DB_URL = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql://jobapp:jobapp_dev@localhost:5432/jobapp",
)

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(SYNC_DB_URL)
    yield eng
    eng.dispose()


@pytest.fixture
def two_tenants(engine):
    """Create two tenants and return their IDs."""
    t1 = uuid.uuid4()
    t2 = uuid.uuid4()
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (:id, :name, :slug)"),
            [
                {"id": str(t1), "name": "Tenant A", "slug": f"tenant-a-{t1.hex[:8]}"},
                {"id": str(t2), "name": "Tenant B", "slug": f"tenant-b-{t2.hex[:8]}"},
            ],
        )
        conn.commit()
    yield str(t1), str(t2)
    # Cleanup
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM jobs WHERE tenant_id IN (:t1, :t2)"), {"t1": str(t1), "t2": str(t2)})
        conn.execute(text("DELETE FROM tenants WHERE id IN (:t1, :t2)"), {"t1": str(t1), "t2": str(t2)})
        conn.commit()


def test_rls_isolates_tenants(engine, two_tenants):
    """Tenant A cannot see Tenant B's jobs."""
    t1, t2 = two_tenants

    with engine.connect() as conn:
        # Insert a job for each tenant (bypass RLS with superuser)
        conn.execute(text(
            "INSERT INTO jobs (tenant_id, url, url_hash, title, company) "
            "VALUES (:tid, :url, :hash, :title, :company)"
        ), [
            {"tid": t1, "url": "https://a.com/job1", "hash": "hash-a1", "title": "Job A", "company": "CompanyA"},
            {"tid": t2, "url": "https://b.com/job1", "hash": "hash-b1", "title": "Job B", "company": "CompanyB"},
        ])
        conn.commit()

    # Now query as tenant A — should only see Job A
    with engine.connect() as conn:
        conn.execute(text(f"SET app.current_tenant = '{t1}'"))
        rows = conn.execute(text("SELECT title FROM jobs")).fetchall()
        titles = [r[0] for r in rows]
        assert "Job A" in titles
        assert "Job B" not in titles

    # Query as tenant B — should only see Job B
    with engine.connect() as conn:
        conn.execute(text(f"SET app.current_tenant = '{t2}'"))
        rows = conn.execute(text("SELECT title FROM jobs")).fetchall()
        titles = [r[0] for r in rows]
        assert "Job B" in titles
        assert "Job A" not in titles
```

- [ ] **Step 2: Run the integration test**

Run:
```bash
docker compose up -d
cd core && pytest tests/test_rls_integration.py -v -m integration
```

Expected: `test_rls_isolates_tenants PASSED`

**Note:** If RLS blocks the superuser too, you may need to run as the postgres superuser or create a non-superuser role. RLS policies don't apply to table owners by default in PostgreSQL — the `jobapp` user owns the tables, so RLS won't apply to it unless `FORCE ROW LEVEL SECURITY` is used. For this test to work properly, either:
1. The `jobapp` user is the table owner and you add `ALTER TABLE jobs FORCE ROW LEVEL SECURITY;` in the migration, or
2. Create a separate `jobapp_api` role that doesn't own the tables.

If the test fails because RLS is not enforced on the table owner, add this step: update the migration to include `FORCE ROW LEVEL SECURITY` on all RLS tables. In `alembic/versions/001_initial_schema.py`, after the RLS enable line, add:

```python
op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
```

- [ ] **Step 3: Commit**

```bash
git add core/tests/test_rls_integration.py
git commit -m "test: add RLS integration test verifying tenant isolation"
```

---

### Task 9: Create Placeholder Directories for Phase 2 & 3

**Files:**
- Create: `api/.gitkeep`
- Create: `web/.gitkeep`
- Update: `.gitignore`

- [ ] **Step 1: Create placeholder directories**

```bash
mkdir -p api web
touch api/.gitkeep web/.gitkeep
```

- [ ] **Step 2: Update .gitignore**

Add these lines to `.gitignore`:

```
# Superpowers brainstorm sessions
.superpowers/

# Node (web/)
web/node_modules/
web/dist/

# Python
__pycache__/
*.egg-info/
*.pyc
.eggs/

# Docker volumes (local)
postgres_data/
redis_data/
minio_data/
```

- [ ] **Step 3: Commit**

```bash
git add api/.gitkeep web/.gitkeep .gitignore
git commit -m "chore: add placeholder dirs for api/ and web/, update .gitignore"
```

---

### Task 10: Verify Full Phase 1 Works End-to-End

- [ ] **Step 1: Start infrastructure**

```bash
docker compose up -d
docker compose ps  # all healthy
```

- [ ] **Step 2: Run migrations**

```bash
alembic upgrade head
```

- [ ] **Step 3: Run all core tests**

```bash
cd core && pytest -v --tb=short
```

Expected: All existing tests pass + new tests pass.

- [ ] **Step 4: Run integration test**

```bash
cd core && pytest tests/test_rls_integration.py -v -m integration
```

Expected: PASS

- [ ] **Step 5: Verify CLI still works**

```bash
job --help
job list
```

Expected: CLI outputs help and job list (empty or existing data).

- [ ] **Step 6: Final commit if any fixes were needed**

```bash
git status  # check for uncommitted fixes
# If changes exist:
git add -A
git commit -m "fix: address issues found during Phase 1 end-to-end verification"
```
