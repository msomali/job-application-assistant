# Phase 2: FastAPI Backend — Auth, Routes, Workers, SSE

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI API layer that wraps core/ functionality behind authenticated, tenant-scoped REST endpoints with Celery background workers and SSE real-time updates.

**Architecture:** `api/` is a separate installable package that imports `job-core`. FastAPI handles HTTP, middleware sets RLS tenant context per request, Celery workers run long tasks (scrape/analyze/generate), SSE pushes progress to the frontend via Redis pub/sub.

**Tech Stack:** FastAPI, fastapi-users, Celery, Redis, SQLAlchemy (async), Pydantic v2, SSE (sse-starlette), httpx (test client)

**Prerequisites:** Phase 1 complete — Docker infra running, core/ package installable, PostgreSQL with RLS, Alembic migrations applied.

---

## File Structure

```
api/
├── pyproject.toml                  # installable package, depends on job-core
├── src/
│   ├── __init__.py
│   ├── app.py                      # FastAPI app factory, lifespan, CORS, routers
│   ├── config.py                   # Pydantic Settings for API config
│   ├── deps.py                     # FastAPI dependencies (db session, current user, tenant)
│   ├── schemas.py                  # Pydantic request/response schemas
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── backend.py              # fastapi-users JWT backend + cookie transport
│   │   ├── manager.py              # UserManager with tenant-aware create
│   │   └── models.py               # fastapi-users SQLAlchemy adapter glue
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── tenant.py               # Sets RLS app.current_tenant per request
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── profile.py              # GET/PUT /api/profile, import/export
│   │   ├── jobs.py                 # CRUD + scrape/analyze/generate endpoints
│   │   ├── discovery.py            # Search config CRUD + run
│   │   ├── search.py               # Indeed + LinkedIn search
│   │   ├── skills.py               # Analytics endpoints
│   │   ├── answers.py              # Answer CRUD + import + stats
│   │   ├── billing.py              # Plan, usage, history (stubs)
│   │   ├── tasks.py                # Task status + SSE stream
│   │   └── admin.py                # Tenant admin endpoints
│   └── workers/
│       ├── __init__.py
│       ├── celery_app.py           # Celery app + config
│       └── tasks.py                # scrape_job, analyze_job, generate_docs, run_discovery
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # TestClient fixtures, test DB, mock celery
│   ├── test_auth.py
│   ├── test_profile.py
│   ├── test_jobs.py
│   ├── test_discovery.py
│   ├── test_skills.py
│   ├── test_answers.py
│   ├── test_billing.py
│   ├── test_tasks.py
│   └── test_workers.py
```

---

### Task 1: API Package Scaffold + Config

**Files:**
- Create: `api/pyproject.toml`
- Create: `api/src/__init__.py`
- Create: `api/src/config.py`
- Create: `api/src/app.py`
- Create: `api/tests/__init__.py`

- [ ] **Step 1: Create api/pyproject.toml**

```toml
[project]
name = "job-api"
version = "0.1.0"
description = "FastAPI backend for Job Application Assistant"
requires-python = ">=3.11"
dependencies = [
    "job-core @ file:///../core",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "fastapi-users[sqlalchemy]>=14.0",
    "celery[redis]>=5.4",
    "redis>=5.0",
    "sse-starlette>=2.0",
    "python-multipart>=0.0.18",
    "pydantic-settings>=2.7",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.28",
    "ruff>=0.4",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["src*"]

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
ignore = ["S608", "S603", "S110", "S112", "E501", "E402"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101"]
```

- [ ] **Step 2: Create api/src/__init__.py**

```python
```

(Empty file.)

- [ ] **Step 3: Create api/src/config.py**

```python
"""API configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://jobapp_api:jobapp_dev@localhost:5432/jobapp"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_lifetime_seconds: int = 900  # 15 minutes
    jwt_refresh_lifetime_seconds: int = 604800  # 7 days

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin"

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


settings = Settings()
```

- [ ] **Step 4: Create api/src/app.py**

```python
"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Job Application Assistant API", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app = create_app()
```

- [ ] **Step 5: Create api/tests/__init__.py**

```python
```

(Empty file.)

- [ ] **Step 6: Verify the app starts**

Run: `cd api && pip install -e ".[dev]" && python -c "from src.app import app; print(app.title)"`
Expected: `Job Application Assistant API`

- [ ] **Step 7: Commit**

```bash
git add api/
git commit -m "feat(api): scaffold FastAPI package with config and app factory"
```

---

### Task 2: FastAPI Dependencies + Tenant Middleware

**Files:**
- Create: `api/src/deps.py`
- Create: `api/src/middleware/__init__.py`
- Create: `api/src/middleware/tenant.py`
- Modify: `api/src/app.py` (add middleware)
- Create: `api/tests/conftest.py`

- [ ] **Step 1: Create api/src/deps.py**

```python
"""FastAPI dependency injection — DB session, current user, tenant context."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.pg import get_session_factory, set_tenant_context


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session, closing it after the request."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def get_tenant_session(
    tenant_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a DB session with RLS tenant context set."""
    await set_tenant_context(session, tenant_id)
    yield session
```

Note: The `tenant_id` will come from the authenticated user's JWT claims. The full wiring happens in Task 3 when we add auth. For now, `get_tenant_session` takes `tenant_id` as a parameter.

- [ ] **Step 2: Create api/src/middleware/__init__.py**

```python
```

(Empty file.)

- [ ] **Step 3: Create api/src/middleware/tenant.py**

```python
"""Middleware that sets the RLS tenant context from the authenticated user's JWT."""

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Paths that don't require tenant context
_PUBLIC_PATHS = frozenset({
    "/docs", "/openapi.json", "/redoc", "/healthz",
})


class TenantMiddleware(BaseHTTPMiddleware):
    """Extract tenant_id from request state (set by auth) and store for deps."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip public paths and auth routes
        if request.url.path in _PUBLIC_PATHS or request.url.path.startswith("/api/auth"):
            return await call_next(request)

        # tenant_id is set on request.state by the auth dependency
        # If not present, the request is unauthenticated (handled by route deps)
        return await call_next(request)
```

- [ ] **Step 4: Add middleware to app.py and health endpoint**

Update `api/src/app.py`:

```python
"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.middleware.tenant import TenantMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Job Application Assistant API", lifespan=lifespan)

    app.add_middleware(TenantMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 5: Create api/tests/conftest.py**

```python
"""Shared test fixtures for API tests."""

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.app import create_app
from src.deps import get_db_session


@pytest.fixture
def mock_session():
    """Mock async DB session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def app(mock_session):
    """Create test app with mocked DB."""
    test_app = create_app()

    async def override_get_db():
        yield mock_session

    test_app.dependency_overrides[get_db_session] = override_get_db
    return test_app


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def tenant_id() -> str:
    return str(uuid.uuid4())
```

- [ ] **Step 6: Write test for health endpoint**

Create `api/tests/test_health.py`:

```python
"""Test health endpoint."""

import pytest


@pytest.mark.asyncio
async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 7: Run test**

Run: `cd api && python -m pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add api/
git commit -m "feat(api): add dependencies, tenant middleware, health endpoint with tests"
```

---

### Task 3: Authentication with fastapi-users

**Files:**
- Create: `api/src/auth/__init__.py`
- Create: `api/src/auth/models.py`
- Create: `api/src/auth/manager.py`
- Create: `api/src/auth/backend.py`
- Modify: `api/src/deps.py` (add current_user dependency)
- Modify: `api/src/app.py` (register auth routers)
- Create: `api/tests/test_auth.py`

- [ ] **Step 1: Create api/src/auth/__init__.py**

```python
```

(Empty file.)

- [ ] **Step 2: Create api/src/auth/models.py**

This bridges our existing `User` ORM model with fastapi-users. fastapi-users needs specific protocols, but our User model already has the right fields (`id`, `email`, `hashed_password`, `is_active`, `is_verified`).

```python
"""fastapi-users SQLAlchemy adapter using our existing User model."""

from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User


class UserDatabase(SQLAlchemyUserDatabase):
    """Adapter that tells fastapi-users to use our User table."""
    pass


async def get_user_db(session: AsyncSession):
    yield UserDatabase(session, User)
```

- [ ] **Step 3: Create api/src/auth/manager.py**

```python
"""User manager — handles registration, password hashing, tenant creation."""

import uuid

from fastapi import Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from sqlalchemy import text

from src.db.models import Tenant, User, UserProfile


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = "change-me"  # Overridden from settings at startup
    verification_token_secret = "change-me"

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        """After registration: create tenant + profile if user doesn't have one yet."""
        session = self.user_db.session

        if user.tenant_id is None:
            # New user — create a tenant for them
            tenant = Tenant(
                name=user.email.split("@")[0],
                slug=f"t-{uuid.uuid4().hex[:12]}",
            )
            session.add(tenant)
            await session.flush()
            user.tenant_id = tenant.id
            user.role = "owner"
            session.add(user)

        # Create empty profile
        profile = UserProfile(
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
        session.add(profile)
        await session.commit()
```

- [ ] **Step 4: Create api/src/auth/backend.py**

```python
"""JWT authentication backend for fastapi-users."""

import uuid

from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, BearerTransport, JWTStrategy
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.manager import UserManager
from src.auth.models import get_user_db
from src.config import settings
from src.db.models import User
from src.deps import get_db_session


bearer_transport = BearerTransport(tokenUrl="/api/auth/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.jwt_secret, lifetime_seconds=settings.jwt_lifetime_seconds)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)


async def get_user_manager(session: AsyncSession = Depends(get_db_session)):
    user_db = get_user_db(session)
    # get_user_db is an async generator — need to advance it
    db = await user_db.__anext__()
    yield UserManager(db)


fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
```

- [ ] **Step 5: Update deps.py with tenant-aware session**

Replace `api/src/deps.py`:

```python
"""FastAPI dependency injection — DB session, current user, tenant context."""

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User
from src.db.pg import get_session_factory, set_tenant_context


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session, closing it after the request."""
    factory = get_session_factory()
    async with factory() as session:
        yield session


async def get_tenant_session(
    session: AsyncSession = Depends(get_db_session),
    user: "User" = Depends(lambda: None),  # Replaced by auth in routes
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a DB session with RLS tenant context set."""
    if user and user.tenant_id:
        await set_tenant_context(session, str(user.tenant_id))
    yield session
```

- [ ] **Step 6: Register auth routers in app.py**

Update `api/src/app.py`:

```python
"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.auth.backend import auth_backend, fastapi_users
from src.auth.manager import UserManager
from src.config import settings
from src.middleware.tenant import TenantMiddleware
from src.schemas import UserCreate, UserRead


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set secrets from settings
    UserManager.reset_password_token_secret = settings.jwt_secret
    UserManager.verification_token_secret = settings.jwt_secret
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Job Application Assistant API", lifespan=lifespan)

    app.add_middleware(TenantMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth routes
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/api/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/api/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_reset_password_router(),
        prefix="/api/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_verify_router(UserRead),
        prefix="/api/auth",
        tags=["auth"],
    )

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 7: Create Pydantic schemas (api/src/schemas.py)**

```python
"""Pydantic request/response schemas."""

import uuid
from datetime import datetime

from fastapi_users import schemas
from pydantic import BaseModel


# --- Auth schemas (fastapi-users) ---

class UserRead(schemas.BaseUser[uuid.UUID]):
    tenant_id: uuid.UUID | None = None
    role: str = "member"


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass


# --- Profile schemas ---

class ContactInfo(BaseModel):
    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    github: str | None = None
    website: str | None = None


class ExperienceEntry(BaseModel):
    company: str
    title: str
    dates: str | None = None
    bullets: list[str] = []


class EducationEntry(BaseModel):
    school: str
    degree: str
    dates: str | None = None


class ProjectEntry(BaseModel):
    name: str
    description: str | None = None
    url: str | None = None
    tech: list[str] = []


class ProfileRead(BaseModel):
    id: uuid.UUID
    full_name: str | None = None
    contact: ContactInfo | None = None
    summary: str | None = None
    experience: list[ExperienceEntry] = []
    education: list[EducationEntry] = []
    skills: list[str] = []
    certifications: list[str] = []
    projects: list[ProjectEntry] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    contact: ContactInfo | None = None
    summary: str | None = None
    experience: list[ExperienceEntry] | None = None
    education: list[EducationEntry] | None = None
    skills: list[str] | None = None
    certifications: list[str] | None = None
    projects: list[ProjectEntry] | None = None


# --- Job schemas ---

class JobRead(BaseModel):
    id: int
    url: str
    title: str
    company: str
    location: str | None = None
    salary_range: str | None = None
    job_type: str | None = None
    experience_level: str | None = None
    description: str | None = None
    requirements: list = []
    responsibilities: list = []
    benefits: list = []
    application_url: str | None = None
    date_posted: str | None = None
    scraped_at: datetime

    model_config = {"from_attributes": True}


class JobScrapeRequest(BaseModel):
    url: str


class AnalysisRead(BaseModel):
    id: int
    job_id: int
    fit_score: int
    base_score: int | None = None
    penalties: list = []
    fit_reasoning: str | None = None
    matching_skills: list = []
    gaps: list = []
    keywords: list = []
    tailoring_strategy: str | None = None
    analyzed_at: datetime

    model_config = {"from_attributes": True}


# --- Task schemas ---

class TaskRead(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    progress: int = 0
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskCreate(BaseModel):
    type: str
    input: dict | None = None


# --- Discovery schemas ---

class SearchConfigRead(BaseModel):
    id: int
    name: str
    config_type: str
    config: dict
    is_active: bool
    last_run_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchConfigCreate(BaseModel):
    name: str
    config_type: str  # 'search_query' or 'career_page'
    config: dict


class SearchConfigUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    is_active: bool | None = None


# --- Answer schemas ---

class AnswerRead(BaseModel):
    id: int
    question: str
    answer: str
    source: str = "manual"
    category: str | None = None
    times_used: int = 0
    last_used_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnswerCreate(BaseModel):
    question: str
    answer: str
    category: str | None = None


class AnswerUpdate(BaseModel):
    answer: str | None = None
    category: str | None = None


# --- Billing schemas ---

class PlanRead(BaseModel):
    plan: str
    limits: dict


class UsageRead(BaseModel):
    period_start: datetime
    period_end: datetime
    scrapes: int = 0
    analyses: int = 0
    generations: int = 0
    tokens_used: int = 0
    cost_estimate: float = 0.0


# --- Skill schemas ---

class SkillCount(BaseModel):
    skill: str
    count: int


class SkillGap(BaseModel):
    skill: str
    demand_count: int
```

- [ ] **Step 8: Write auth tests**

Create `api/tests/test_auth.py`:

```python
"""Test auth endpoints exist and return expected status codes."""

import pytest


@pytest.mark.asyncio
async def test_login_requires_credentials(client):
    resp = await client.post("/api/auth/login", data={"username": "", "password": ""})
    # fastapi-users returns 400 or 422 for missing/invalid credentials
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_register_endpoint_exists(client):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "testpassword123"},
    )
    # Will fail at DB level (mocked), but endpoint should exist (not 404)
    assert resp.status_code != 404
```

- [ ] **Step 9: Run tests**

Run: `cd api && python -m pytest tests/ -v`
Expected: All tests pass (health + auth endpoint existence)

- [ ] **Step 10: Commit**

```bash
git add api/
git commit -m "feat(api): add fastapi-users auth with JWT, schemas, registration with auto-tenant"
```

---

### Task 4: Celery Workers + Task Tracking

**Files:**
- Create: `api/src/workers/__init__.py`
- Create: `api/src/workers/celery_app.py`
- Create: `api/src/workers/tasks.py`
- Create: `api/src/routes/__init__.py`
- Create: `api/src/routes/tasks.py`
- Modify: `api/src/app.py` (register tasks router)
- Create: `api/tests/test_workers.py`
- Create: `api/tests/test_tasks.py`

- [ ] **Step 1: Create api/src/workers/__init__.py**

```python
```

(Empty file.)

- [ ] **Step 2: Create api/src/workers/celery_app.py**

```python
"""Celery app configuration."""

from celery import Celery

from src.config import settings

celery_app = Celery(
    "jobapp",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.autodiscover_tasks(["src.workers"])
```

- [ ] **Step 3: Create api/src/workers/tasks.py**

```python
"""Celery task definitions for background jobs."""

import asyncio
import json
import logging
import uuid

import redis
from sqlalchemy import select

from src.config import settings
from src.db.models import Task as TaskModel
from src.db.pg import get_session_factory, set_tenant_context
from src.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_redis = None


def _get_redis():
    global _redis
    if _redis is None:
        _redis = redis.from_url(settings.redis_url)
    return _redis


def _publish_event(tenant_id: str, event_type: str, data: dict):
    """Publish SSE event to Redis pub/sub."""
    _get_redis().publish(
        f"tenant:{tenant_id}:events",
        json.dumps({"event": event_type, "data": data}),
    )


async def _update_task(task_id: str, tenant_id: str, **fields):
    """Update task record in DB."""
    factory = get_session_factory()
    async with factory() as session:
        await set_tenant_context(session, tenant_id)
        result = await session.execute(
            select(TaskModel).where(TaskModel.id == uuid.UUID(task_id))
        )
        task = result.scalar_one_or_none()
        if task:
            for k, v in fields.items():
                setattr(task, k, v)
            await session.commit()


def _run_async(coro):
    """Run async code from sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="scrape_job")
def scrape_job(self, task_id: str, tenant_id: str, url: str):
    """Scrape a job URL, extract details, save to DB."""
    _run_async(_update_task(task_id, tenant_id, status="running", progress=10))
    _publish_event(tenant_id, "task:started", {"task_id": task_id, "type": "scrape"})

    try:
        from src.scraper.firecrawl_client import scrape_and_extract
        job_data = scrape_and_extract(url)

        _run_async(_update_task(task_id, tenant_id, status="running", progress=50))
        _publish_event(tenant_id, "task:progress", {
            "task_id": task_id, "type": "scrape", "progress": 50, "message": "Extracted job data",
        })

        # Save job to DB
        from src.db.models import Job
        import hashlib
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]

        async def _save():
            factory = get_session_factory()
            async with factory() as session:
                await set_tenant_context(session, tenant_id)
                job = Job(
                    tenant_id=uuid.UUID(tenant_id),
                    url=url,
                    url_hash=url_hash,
                    title=job_data.get("title", "Unknown"),
                    company=job_data.get("company", "Unknown"),
                    location=job_data.get("location"),
                    salary_range=job_data.get("salary_range"),
                    job_type=job_data.get("job_type"),
                    experience_level=job_data.get("experience_level"),
                    description=job_data.get("description"),
                    requirements=job_data.get("requirements", []),
                    responsibilities=job_data.get("responsibilities", []),
                    benefits=job_data.get("benefits", []),
                    application_url=job_data.get("application_url"),
                    date_posted=job_data.get("date_posted"),
                    raw_markdown=job_data.get("raw_markdown"),
                )
                session.add(job)
                await session.commit()
                await session.refresh(job)
                return job.id

        job_id = _run_async(_save())

        _run_async(_update_task(
            task_id, tenant_id, status="completed", progress=100,
            result={"job_id": job_id},
        ))
        _publish_event(tenant_id, "task:completed", {
            "task_id": task_id, "type": "scrape", "result": {"job_id": job_id},
        })

    except Exception as e:
        logger.exception("scrape_job failed: %s", e)
        _run_async(_update_task(task_id, tenant_id, status="failed", error=str(e)))
        _publish_event(tenant_id, "task:failed", {
            "task_id": task_id, "type": "scrape", "error": str(e),
        })
        raise


@celery_app.task(bind=True, name="analyze_job")
def analyze_job(self, task_id: str, tenant_id: str, job_id: int):
    """Analyze a job against the user's profile."""
    _run_async(_update_task(task_id, tenant_id, status="running", progress=10))
    _publish_event(tenant_id, "task:started", {"task_id": task_id, "type": "analyze"})

    try:
        # Fetch job from DB
        async def _fetch_job():
            factory = get_session_factory()
            async with factory() as session:
                await set_tenant_context(session, tenant_id)
                result = await session.execute(
                    select(Job).where(Job.id == job_id)
                )
                return result.scalar_one_or_none()

        from src.db.models import Job, Analysis, UserProfile
        job = _run_async(_fetch_job())
        if not job:
            raise ValueError(f"Job {job_id} not found")

        _run_async(_update_task(task_id, tenant_id, progress=30))

        # Fetch user profile for analysis
        async def _fetch_profile():
            factory = get_session_factory()
            async with factory() as session:
                await set_tenant_context(session, tenant_id)
                result = await session.execute(
                    select(UserProfile).where(UserProfile.tenant_id == uuid.UUID(tenant_id))
                )
                return result.scalar_one_or_none()

        profile = _run_async(_fetch_profile())

        # Build job posting dict for analyzer
        from src.analyzer.job_analyzer import analyze_job as core_analyze
        from src.models import JobPosting

        job_posting = JobPosting(
            url=job.url,
            title=job.title,
            company=job.company,
            location=job.location or "",
            description=job.description or "",
            requirements=job.requirements or [],
            responsibilities=job.responsibilities or [],
            benefits=job.benefits or [],
            salary_range=job.salary_range,
            job_type=job.job_type,
            experience_level=job.experience_level,
            application_url=job.application_url,
            date_posted=job.date_posted,
        )

        # Convert profile to resume dict for analyzer
        resume_data = {}
        if profile and profile.raw_json:
            resume_data = profile.raw_json
        elif profile:
            resume_data = {
                "full_name": profile.full_name,
                "skills": profile.skills or [],
                "experience": profile.experience or [],
                "education": profile.education or [],
            }

        _run_async(_update_task(task_id, tenant_id, progress=50))

        analysis_result = core_analyze(job_posting, resume_data)

        # Save analysis
        async def _save_analysis():
            factory = get_session_factory()
            async with factory() as session:
                await set_tenant_context(session, tenant_id)
                analysis = Analysis(
                    tenant_id=uuid.UUID(tenant_id),
                    job_id=job_id,
                    fit_score=analysis_result.fit_score,
                    base_score=analysis_result.base_score,
                    penalties=[p.model_dump() for p in analysis_result.penalties] if hasattr(analysis_result, 'penalties') else [],
                    fit_reasoning=analysis_result.fit_reasoning,
                    matching_skills=analysis_result.matching_skills,
                    gaps=analysis_result.gaps,
                    keywords=analysis_result.keywords,
                    tailoring_strategy=analysis_result.tailoring_strategy,
                )
                session.add(analysis)
                await session.commit()
                return analysis.id

        analysis_id = _run_async(_save_analysis())

        _run_async(_update_task(
            task_id, tenant_id, status="completed", progress=100,
            result={"analysis_id": analysis_id, "fit_score": analysis_result.fit_score},
        ))
        _publish_event(tenant_id, "task:completed", {
            "task_id": task_id, "type": "analyze",
            "result": {"analysis_id": analysis_id, "fit_score": analysis_result.fit_score},
        })

    except Exception as e:
        logger.exception("analyze_job failed: %s", e)
        _run_async(_update_task(task_id, tenant_id, status="failed", error=str(e)))
        _publish_event(tenant_id, "task:failed", {
            "task_id": task_id, "type": "analyze", "error": str(e),
        })
        raise


@celery_app.task(bind=True, name="generate_docs")
def generate_docs(self, task_id: str, tenant_id: str, job_id: int):
    """Generate resume + cover letter for a job."""
    _run_async(_update_task(task_id, tenant_id, status="running", progress=10))
    _publish_event(tenant_id, "task:started", {"task_id": task_id, "type": "generate"})

    try:
        _run_async(_update_task(
            task_id, tenant_id, status="completed", progress=100,
            result={"message": "Document generation placeholder — full implementation in Phase 3"},
        ))
        _publish_event(tenant_id, "task:completed", {
            "task_id": task_id, "type": "generate", "result": {"status": "placeholder"},
        })
    except Exception as e:
        logger.exception("generate_docs failed: %s", e)
        _run_async(_update_task(task_id, tenant_id, status="failed", error=str(e)))
        _publish_event(tenant_id, "task:failed", {
            "task_id": task_id, "type": "generate", "error": str(e),
        })
        raise


@celery_app.task(bind=True, name="run_discovery")
def run_discovery(self, task_id: str, tenant_id: str):
    """Run all active search configs for a tenant."""
    _run_async(_update_task(task_id, tenant_id, status="running", progress=10))
    _publish_event(tenant_id, "task:started", {"task_id": task_id, "type": "discover"})

    try:
        _run_async(_update_task(
            task_id, tenant_id, status="completed", progress=100,
            result={"message": "Discovery placeholder — wired to core in Phase 3"},
        ))
        _publish_event(tenant_id, "task:completed", {
            "task_id": task_id, "type": "discover", "result": {"status": "placeholder"},
        })
    except Exception as e:
        logger.exception("run_discovery failed: %s", e)
        _run_async(_update_task(task_id, tenant_id, status="failed", error=str(e)))
        _publish_event(tenant_id, "task:failed", {
            "task_id": task_id, "type": "discover", "error": str(e),
        })
        raise
```

- [ ] **Step 4: Create api/src/routes/__init__.py**

```python
```

(Empty file.)

- [ ] **Step 5: Create api/src/routes/tasks.py**

```python
"""Task status and SSE streaming endpoints."""

import asyncio
import json
import logging
import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from src.auth.backend import current_active_user
from src.config import settings
from src.db.models import Task as TaskModel
from src.db.models import User
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import TaskRead

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(TaskModel).where(TaskModel.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("", response_model=list[TaskRead])
async def list_tasks(
    limit: int = 20,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(TaskModel).order_by(TaskModel.created_at.desc()).limit(limit)
    )
    return result.scalars().all()


@router.get("/stream")
async def task_stream(user: User = Depends(current_active_user)):
    """SSE endpoint — streams task events for the current tenant."""
    tenant_id = str(user.tenant_id)

    async def event_generator():
        r = aioredis.from_url(settings.redis_url)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"tenant:{tenant_id}:events")
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30)
                if message and message["type"] == "message":
                    data = json.loads(message["data"])
                    yield {"event": data["event"], "data": json.dumps(data["data"])}
                else:
                    # Send keepalive
                    yield {"event": "ping", "data": ""}
        finally:
            await pubsub.unsubscribe(f"tenant:{tenant_id}:events")
            await r.aclose()

    return EventSourceResponse(event_generator())
```

- [ ] **Step 6: Register tasks router in app.py**

Add to the `create_app()` function in `api/src/app.py`, after auth routers:

```python
    from src.routes.tasks import router as tasks_router
    app.include_router(tasks_router)
```

- [ ] **Step 7: Write worker tests**

Create `api/tests/test_workers.py`:

```python
"""Test Celery task definitions."""

from unittest.mock import patch, MagicMock

from src.workers.celery_app import celery_app


def test_celery_app_configured():
    assert celery_app.main == "jobapp"
    assert celery_app.conf.task_serializer == "json"


def test_task_registered():
    # After importing tasks module, tasks should be discoverable
    from src.workers import tasks  # noqa: F401
    task_names = list(celery_app.tasks.keys())
    assert "scrape_job" in task_names
    assert "analyze_job" in task_names
    assert "generate_docs" in task_names
    assert "run_discovery" in task_names
```

- [ ] **Step 8: Write tasks route tests**

Create `api/tests/test_tasks.py`:

```python
"""Test task API endpoints."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.db.models import Task as TaskModel


@pytest.mark.asyncio
async def test_list_tasks_requires_auth(client):
    resp = await client.get("/api/tasks")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_task_requires_auth(client):
    resp = await client.get(f"/api/tasks/{uuid.uuid4()}")
    assert resp.status_code == 401
```

- [ ] **Step 9: Run tests**

Run: `cd api && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 10: Commit**

```bash
git add api/
git commit -m "feat(api): add Celery workers with task tracking and SSE streaming"
```

---

### Task 5: Profile Routes

**Files:**
- Create: `api/src/routes/profile.py`
- Modify: `api/src/app.py` (register router)
- Create: `api/tests/test_profile.py`

- [ ] **Step 1: Create api/src/routes/profile.py**

```python
"""User profile endpoints — CRUD + JSON import/export."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import User, UserProfile
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import ProfileRead, ProfileUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/profile", tags=["profile"])


async def _get_profile(session: AsyncSession, user: User) -> UserProfile:
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.get("", response_model=ProfileRead)
async def get_profile(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    return await _get_profile(session, user)


@router.put("", response_model=ProfileRead)
async def update_profile(
    data: ProfileUpdate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    profile = await _get_profile(session, user)
    update_data = data.model_dump(exclude_unset=True)
    # Convert nested models to dicts for JSONB/ARRAY storage
    if "contact" in update_data and update_data["contact"] is not None:
        update_data["contact"] = data.contact.model_dump()
    if "experience" in update_data and update_data["experience"] is not None:
        update_data["experience"] = [e.model_dump() for e in data.experience]
    if "education" in update_data and update_data["education"] is not None:
        update_data["education"] = [e.model_dump() for e in data.education]
    if "projects" in update_data and update_data["projects"] is not None:
        update_data["projects"] = [p.model_dump() for p in data.projects]

    for field, value in update_data.items():
        setattr(profile, field, value)
    await session.commit()
    await session.refresh(profile)
    return profile


@router.post("/import", response_model=ProfileRead)
async def import_profile(
    raw_json: dict,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Import a profile from master_resume.json format."""
    profile = await _get_profile(session, user)
    profile.raw_json = raw_json
    profile.full_name = raw_json.get("full_name") or raw_json.get("name")
    profile.contact = raw_json.get("contact", {})
    profile.summary = raw_json.get("summary")
    profile.experience = raw_json.get("experience", [])
    profile.education = raw_json.get("education", [])
    profile.skills = raw_json.get("skills", [])
    profile.certifications = raw_json.get("certifications", [])
    profile.projects = raw_json.get("projects", [])
    await session.commit()
    await session.refresh(profile)
    return profile


@router.get("/export")
async def export_profile(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Export profile as JSON (master_resume.json format)."""
    profile = await _get_profile(session, user)
    if profile.raw_json:
        return profile.raw_json
    return {
        "full_name": profile.full_name,
        "contact": profile.contact,
        "summary": profile.summary,
        "experience": profile.experience,
        "education": profile.education,
        "skills": profile.skills,
        "certifications": profile.certifications,
        "projects": profile.projects,
    }
```

- [ ] **Step 2: Register profile router in app.py**

Add to `create_app()` in `api/src/app.py`:

```python
    from src.routes.profile import router as profile_router
    app.include_router(profile_router)
```

- [ ] **Step 3: Write profile tests**

Create `api/tests/test_profile.py`:

```python
"""Test profile endpoints."""

import pytest


@pytest.mark.asyncio
async def test_get_profile_requires_auth(client):
    resp = await client.get("/api/profile")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_profile_requires_auth(client):
    resp = await client.put("/api/profile", json={"full_name": "Test"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_import_profile_requires_auth(client):
    resp = await client.post("/api/profile/import", json={"name": "Test"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_export_profile_requires_auth(client):
    resp = await client.get("/api/profile/export")
    assert resp.status_code == 401
```

- [ ] **Step 4: Run tests**

Run: `cd api && python -m pytest tests/test_profile.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add api/src/routes/profile.py api/tests/test_profile.py api/src/app.py
git commit -m "feat(api): add profile CRUD endpoints with JSON import/export"
```

---

### Task 6: Jobs Routes

**Files:**
- Create: `api/src/routes/jobs.py`
- Modify: `api/src/app.py` (register router)
- Create: `api/tests/test_jobs.py`

- [ ] **Step 1: Create api/src/routes/jobs.py**

```python
"""Job endpoints — list, detail, scrape, analyze, generate, documents."""

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import Analysis, Application, Job, Task as TaskModel, User
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import AnalysisRead, JobRead, JobScrapeRequest, TaskRead

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
async def list_jobs(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query("scraped_at", pattern="^(scraped_at|title|company)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    search: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    query = select(Job)
    if search:
        query = query.where(
            Job.title.ilike(f"%{search}%") | Job.company.ilike(f"%{search}%")
        )
    sort_col = getattr(Job, sort_by)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/ranked", response_model=list[JobRead])
async def ranked_jobs(
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Get jobs ranked by fit score (highest first)."""
    await set_tenant_context(session, str(user.tenant_id))
    query = (
        select(Job)
        .join(Analysis, Analysis.job_id == Job.id)
        .order_by(Analysis.fit_score.desc())
        .limit(limit)
    )
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await session.delete(job)
    await session.commit()


@router.post("/scrape", response_model=TaskRead, status_code=201)
async def scrape_job(
    request: JobScrapeRequest,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Enqueue a job scraping task."""
    await set_tenant_context(session, str(user.tenant_id))
    task = TaskModel(
        tenant_id=user.tenant_id,
        type="scrape",
        input={"url": str(request.url)},
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    from src.workers.tasks import scrape_job as scrape_task
    scrape_task.delay(str(task.id), str(user.tenant_id), str(request.url))

    return task


@router.get("/{job_id}/analysis", response_model=AnalysisRead)
async def get_analysis(
    job_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(Analysis).where(Analysis.job_id == job_id).order_by(Analysis.analyzed_at.desc())
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this job")
    return analysis


@router.post("/{job_id}/analyze", response_model=TaskRead, status_code=201)
async def analyze_job(
    job_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Enqueue a job analysis task."""
    await set_tenant_context(session, str(user.tenant_id))
    # Verify job exists
    result = await session.execute(select(Job).where(Job.id == job_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Job not found")

    task = TaskModel(
        tenant_id=user.tenant_id,
        type="analyze",
        input={"job_id": job_id},
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    from src.workers.tasks import analyze_job as analyze_task
    analyze_task.delay(str(task.id), str(user.tenant_id), job_id)

    return task


@router.post("/{job_id}/generate", response_model=TaskRead, status_code=201)
async def generate_docs(
    job_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Enqueue document generation task."""
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(Job).where(Job.id == job_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Job not found")

    task = TaskModel(
        tenant_id=user.tenant_id,
        type="generate",
        input={"job_id": job_id},
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    from src.workers.tasks import generate_docs as generate_task
    generate_task.delay(str(task.id), str(user.tenant_id), job_id)

    return task


@router.get("/{job_id}/documents")
async def get_documents(
    job_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Get pre-signed URLs for generated documents."""
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(Application).where(Application.job_id == job_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        return {"resume_url": None, "cover_letter_url": None}

    from src.storage import StorageClient
    storage = StorageClient()
    docs = {}
    if app.resume_path:
        docs["resume_url"] = storage.get_document_url(app.resume_path)
    if app.cover_letter_path:
        docs["cover_letter_url"] = storage.get_document_url(app.cover_letter_path)
    return docs
```

- [ ] **Step 2: Register jobs router in app.py**

Add to `create_app()`:

```python
    from src.routes.jobs import router as jobs_router
    app.include_router(jobs_router)
```

- [ ] **Step 3: Write jobs tests**

Create `api/tests/test_jobs.py`:

```python
"""Test job endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_jobs_requires_auth(client):
    resp = await client.get("/api/jobs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_job_requires_auth(client):
    resp = await client.get("/api/jobs/1")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_scrape_job_requires_auth(client):
    resp = await client.post("/api/jobs/scrape", json={"url": "https://example.com/job"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ranked_jobs_requires_auth(client):
    resp = await client.get("/api/jobs/ranked")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_delete_job_requires_auth(client):
    resp = await client.delete("/api/jobs/1")
    assert resp.status_code == 401
```

- [ ] **Step 4: Run tests**

Run: `cd api && python -m pytest tests/test_jobs.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add api/src/routes/jobs.py api/tests/test_jobs.py api/src/app.py
git commit -m "feat(api): add job CRUD, scrape, analyze, generate endpoints"
```

---

### Task 7: Discovery + Search Routes

**Files:**
- Create: `api/src/routes/discovery.py`
- Create: `api/src/routes/search.py`
- Modify: `api/src/app.py` (register routers)
- Create: `api/tests/test_discovery.py`

- [ ] **Step 1: Create api/src/routes/discovery.py**

```python
"""Discovery endpoints — search config CRUD and run."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import SearchConfig, Task as TaskModel, User
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import SearchConfigCreate, SearchConfigRead, SearchConfigUpdate, TaskRead

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/discovery", tags=["discovery"])


@router.get("/configs", response_model=list[SearchConfigRead])
async def list_configs(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(SearchConfig).order_by(SearchConfig.created_at.desc()))
    return result.scalars().all()


@router.post("/configs", response_model=SearchConfigRead, status_code=201)
async def create_config(
    data: SearchConfigCreate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    config = SearchConfig(
        tenant_id=user.tenant_id,
        name=data.name,
        config_type=data.config_type,
        config=data.config,
    )
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config


@router.put("/configs/{config_id}", response_model=SearchConfigRead)
async def update_config(
    config_id: int,
    data: SearchConfigUpdate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(SearchConfig).where(SearchConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(config, field, value)
    await session.commit()
    await session.refresh(config)
    return config


@router.delete("/configs/{config_id}", status_code=204)
async def delete_config(
    config_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(SearchConfig).where(SearchConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    await session.delete(config)
    await session.commit()


@router.post("/run", response_model=TaskRead, status_code=201)
async def run_discovery(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Run all active search configs."""
    await set_tenant_context(session, str(user.tenant_id))
    task = TaskModel(
        tenant_id=user.tenant_id,
        type="discover",
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    from src.workers.tasks import run_discovery as discovery_task
    discovery_task.delay(str(task.id), str(user.tenant_id))

    return task
```

- [ ] **Step 2: Create api/src/routes/search.py**

```python
"""Indeed + LinkedIn search endpoints."""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import Task as TaskModel, User
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import TaskRead

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    location: str | None = None
    limit: int = 10


@router.post("/indeed", response_model=TaskRead, status_code=201)
async def search_indeed(
    request: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    task = TaskModel(
        tenant_id=user.tenant_id,
        type="search_indeed",
        input=request.model_dump(),
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    # Celery task wiring deferred until core search functions are adapted
    return task


@router.post("/linkedin", response_model=TaskRead, status_code=201)
async def search_linkedin(
    request: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    task = TaskModel(
        tenant_id=user.tenant_id,
        type="search_linkedin",
        input=request.model_dump(),
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task
```

- [ ] **Step 3: Register routers in app.py**

Add to `create_app()`:

```python
    from src.routes.discovery import router as discovery_router
    from src.routes.search import router as search_router
    app.include_router(discovery_router)
    app.include_router(search_router)
```

- [ ] **Step 4: Write discovery tests**

Create `api/tests/test_discovery.py`:

```python
"""Test discovery and search endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_configs_requires_auth(client):
    resp = await client.get("/api/discovery/configs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_run_discovery_requires_auth(client):
    resp = await client.post("/api/discovery/run")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_indeed_requires_auth(client):
    resp = await client.post("/api/search/indeed", json={"query": "python developer"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_linkedin_requires_auth(client):
    resp = await client.post("/api/search/linkedin", json={"query": "python developer"})
    assert resp.status_code == 401
```

- [ ] **Step 5: Run tests**

Run: `cd api && python -m pytest tests/test_discovery.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add api/src/routes/discovery.py api/src/routes/search.py api/tests/test_discovery.py api/src/app.py
git commit -m "feat(api): add discovery config CRUD, Indeed and LinkedIn search endpoints"
```

---

### Task 8: Skills, Answers, Billing, Admin Routes

**Files:**
- Create: `api/src/routes/skills.py`
- Create: `api/src/routes/answers.py`
- Create: `api/src/routes/billing.py`
- Create: `api/src/routes/admin.py`
- Modify: `api/src/app.py` (register routers)
- Create: `api/tests/test_skills.py`
- Create: `api/tests/test_answers.py`
- Create: `api/tests/test_billing.py`

- [ ] **Step 1: Create api/src/routes/skills.py**

```python
"""Skill analytics endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import JobSkill, User, UserProfile
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import SkillCount, SkillGap

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("/top", response_model=list[SkillCount])
async def top_skills(
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(JobSkill.skill, func.count(JobSkill.id).label("count"))
        .group_by(JobSkill.skill)
        .order_by(func.count(JobSkill.id).desc())
        .limit(limit)
    )
    return [SkillCount(skill=row[0], count=row[1]) for row in result.all()]


@router.get("/gaps", response_model=list[SkillGap])
async def skill_gaps(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    # Get user's skills
    profile_result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    profile = profile_result.scalar_one_or_none()
    user_skills = set(s.lower() for s in (profile.skills or [])) if profile else set()

    # Get demanded skills
    result = await session.execute(
        select(JobSkill.skill, func.count(JobSkill.id).label("count"))
        .group_by(JobSkill.skill)
        .order_by(func.count(JobSkill.id).desc())
    )
    gaps = []
    for skill, count in result.all():
        if skill.lower() not in user_skills:
            gaps.append(SkillGap(skill=skill, demand_count=count))
    return gaps[:30]


@router.get("/trends")
async def skill_trends(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Skill demand over time — returns raw data for frontend charting."""
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(
            func.date_trunc("week", JobSkill.extracted_at).label("week"),
            JobSkill.skill,
            func.count(JobSkill.id).label("count"),
        )
        .group_by("week", JobSkill.skill)
        .order_by("week")
    )
    return [{"week": str(row[0]), "skill": row[1], "count": row[2]} for row in result.all()]


@router.get("/roles")
async def skills_by_role(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Skills grouped by job experience level."""
    await set_tenant_context(session, str(user.tenant_id))
    from src.db.models import Job
    result = await session.execute(
        select(Job.experience_level, JobSkill.skill, func.count(JobSkill.id).label("count"))
        .join(JobSkill, JobSkill.job_id == Job.id)
        .where(Job.experience_level.isnot(None))
        .group_by(Job.experience_level, JobSkill.skill)
        .order_by(Job.experience_level, func.count(JobSkill.id).desc())
    )
    roles = {}
    for level, skill, count in result.all():
        roles.setdefault(level, []).append({"skill": skill, "count": count})
    return roles
```

- [ ] **Step 2: Create api/src/routes/answers.py**

```python
"""Screening answer CRUD + import + stats."""

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import Answer, User
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import AnswerCreate, AnswerRead, AnswerUpdate

router = APIRouter(prefix="/api/answers", tags=["answers"])


def _hash_question(q: str) -> str:
    return hashlib.sha256(q.strip().lower().encode()).hexdigest()[:16]


@router.get("", response_model=list[AnswerRead])
async def list_answers(
    search: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    query = select(Answer)
    if search:
        query = query.where(Answer.question.ilike(f"%{search}%"))
    query = query.order_by(Answer.created_at.desc()).offset(offset).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


@router.post("", response_model=AnswerRead, status_code=201)
async def create_answer(
    data: AnswerCreate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    answer = Answer(
        tenant_id=user.tenant_id,
        question=data.question,
        question_hash=_hash_question(data.question),
        answer=data.answer,
        category=data.category,
    )
    session.add(answer)
    await session.commit()
    await session.refresh(answer)
    return answer


@router.put("/{answer_id}", response_model=AnswerRead)
async def update_answer(
    answer_id: int,
    data: AnswerUpdate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(Answer).where(Answer.id == answer_id))
    answer = result.scalar_one_or_none()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(answer, field, value)
    await session.commit()
    await session.refresh(answer)
    return answer


@router.delete("/{answer_id}", status_code=204)
async def delete_answer(
    answer_id: int,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(Answer).where(Answer.id == answer_id))
    answer = result.scalar_one_or_none()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    await session.delete(answer)
    await session.commit()


@router.post("/import", status_code=201)
async def import_answers(
    answers: list[dict],
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Bulk import answers from JSON."""
    await set_tenant_context(session, str(user.tenant_id))
    imported = 0
    for entry in answers:
        q = entry.get("question", "")
        a = entry.get("answer", "")
        if not q or not a:
            continue
        answer = Answer(
            tenant_id=user.tenant_id,
            question=q,
            question_hash=_hash_question(q),
            answer=a,
            category=entry.get("category"),
            source="import",
        )
        session.add(answer)
        imported += 1
    await session.commit()
    return {"imported": imported}


@router.get("/stats")
async def answer_stats(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    total = await session.execute(select(func.count(Answer.id)))
    used = await session.execute(select(func.count(Answer.id)).where(Answer.times_used > 0))
    return {
        "total": total.scalar(),
        "used": used.scalar(),
    }
```

- [ ] **Step 3: Create api/src/routes/billing.py**

```python
"""Billing endpoints — plan, usage, history (stubs until Stripe)."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import ApiUsageLog, Tenant, User
from src.db.pg import set_tenant_context
from src.deps import get_db_session

router = APIRouter(prefix="/api/billing", tags=["billing"])

PLAN_LIMITS = {
    "free": {"scrapes_per_day": 10, "analyses_per_day": 20, "generations_per_day": 5},
    "pro": {"scrapes_per_day": 100, "analyses_per_day": 200, "generations_per_day": 50},
    "enterprise": {"scrapes_per_day": 1000, "analyses_per_day": 2000, "generations_per_day": 500},
}


@router.get("/plan")
async def get_plan(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = result.scalar_one()
    limits = PLAN_LIMITS.get(tenant.plan, PLAN_LIMITS["free"])
    return {"plan": tenant.plan, "limits": limits}


@router.get("/usage")
async def get_usage(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    now = datetime.now(timezone.utc)
    period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = await session.execute(
        select(ApiUsageLog.action, func.count(ApiUsageLog.id), func.sum(ApiUsageLog.tokens_used))
        .where(ApiUsageLog.created_at >= period_start)
        .group_by(ApiUsageLog.action)
    )
    usage = {}
    total_tokens = 0
    for action, count, tokens in result.all():
        usage[action] = count
        total_tokens += tokens or 0

    return {
        "period_start": period_start.isoformat(),
        "period_end": now.isoformat(),
        "actions": usage,
        "tokens_used": total_tokens,
    }


@router.get("/usage/history")
async def usage_history(
    days: int = 30,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await session.execute(
        select(
            func.date_trunc("day", ApiUsageLog.created_at).label("day"),
            ApiUsageLog.action,
            func.count(ApiUsageLog.id).label("count"),
        )
        .where(ApiUsageLog.created_at >= since)
        .group_by("day", ApiUsageLog.action)
        .order_by("day")
    )
    return [{"day": str(row[0]), "action": row[1], "count": row[2]} for row in result.all()]


@router.get("/invoices")
async def list_invoices(user: User = Depends(current_active_user)):
    """Stub — returns empty list until Stripe integration."""
    return []
```

- [ ] **Step 4: Create api/src/routes/admin.py**

```python
"""Tenant admin endpoints — user management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import User
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import UserRead

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(user: User):
    if user.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/users", response_model=list[UserRead])
async def list_users(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    _require_admin(user)
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(User).where(User.tenant_id == user.tenant_id)
    )
    return result.scalars().all()


@router.put("/users/{user_id}/role")
async def change_role(
    user_id: str,
    role: str,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    _require_admin(user)
    if role not in ("owner", "admin", "member"):
        raise HTTPException(status_code=400, detail="Invalid role")
    await set_tenant_context(session, str(user.tenant_id))
    import uuid
    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.role = role
    await session.commit()
    return {"status": "ok", "user_id": user_id, "role": role}


@router.delete("/users/{user_id}", status_code=204)
async def remove_user(
    user_id: str,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    _require_admin(user)
    await set_tenant_context(session, str(user.tenant_id))
    import uuid
    if uuid.UUID(user_id) == user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.is_active = False
    await session.commit()
```

- [ ] **Step 5: Register all routers in app.py**

Add to `create_app()`:

```python
    from src.routes.skills import router as skills_router
    from src.routes.answers import router as answers_router
    from src.routes.billing import router as billing_router
    from src.routes.admin import router as admin_router
    app.include_router(skills_router)
    app.include_router(answers_router)
    app.include_router(billing_router)
    app.include_router(admin_router)
```

- [ ] **Step 6: Write tests for skills, answers, billing**

Create `api/tests/test_skills.py`:

```python
"""Test skills endpoints."""

import pytest


@pytest.mark.asyncio
async def test_top_skills_requires_auth(client):
    resp = await client.get("/api/skills/top")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_skill_gaps_requires_auth(client):
    resp = await client.get("/api/skills/gaps")
    assert resp.status_code == 401
```

Create `api/tests/test_answers.py`:

```python
"""Test answers endpoints."""

import pytest


@pytest.mark.asyncio
async def test_list_answers_requires_auth(client):
    resp = await client.get("/api/answers")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_answer_requires_auth(client):
    resp = await client.post("/api/answers", json={"question": "Q", "answer": "A"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_answer_stats_requires_auth(client):
    resp = await client.get("/api/answers/stats")
    assert resp.status_code == 401
```

Create `api/tests/test_billing.py`:

```python
"""Test billing endpoints."""

import pytest


@pytest.mark.asyncio
async def test_get_plan_requires_auth(client):
    resp = await client.get("/api/billing/plan")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_usage_requires_auth(client):
    resp = await client.get("/api/billing/usage")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invoices_requires_auth(client):
    resp = await client.get("/api/billing/invoices")
    assert resp.status_code == 401
```

- [ ] **Step 7: Run all tests**

Run: `cd api && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add api/src/routes/ api/tests/
git commit -m "feat(api): add skills, answers, billing, and admin routes"
```

---

### Task 9: Update Docker Compose + Makefile for API + Worker

**Files:**
- Modify: `docker-compose.yml` (add api, worker services)
- Modify: `docker-compose.dev.yml` (add dev overrides)
- Modify: `Makefile` (add api targets)

- [ ] **Step 1: Add api and worker services to docker-compose.yml**

Append these services to the `services:` section of `docker-compose.yml`:

```yaml
  api:
    build:
      context: .
      dockerfile: api/Dockerfile
    ports:
      - "${API_PORT:-8000}:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://jobapp_api:jobapp_dev@postgres:5432/jobapp
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
      - MINIO_ENDPOINT=minio:9000
      - JWT_SECRET=${JWT_SECRET:-change-me-in-production}
      - CORS_ORIGINS=["http://localhost:5173"]
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy

  worker:
    build:
      context: .
      dockerfile: api/Dockerfile
    command: celery -A src.workers.celery_app worker --loglevel=info --concurrency=4
    environment:
      - DATABASE_URL=postgresql+asyncpg://jobapp_api:jobapp_dev@postgres:5432/jobapp
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
      - MINIO_ENDPOINT=minio:9000
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
```

- [ ] **Step 2: Create api/Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install core first (dependency)
COPY core/ ./core/
RUN pip install --no-cache-dir ./core

# Install api
COPY api/ ./api/
RUN pip install --no-cache-dir ./api

WORKDIR /app/api
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Add dev override for api**

Add to `docker-compose.dev.yml`:

```yaml
  api:
    ports:
      - "8000:8000"
    volumes:
      - ./api:/app/api
      - ./core:/app/core
    command: uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
    environment:
      - CORS_ORIGINS=["http://localhost:5173"]
```

- [ ] **Step 4: Update Makefile**

Add these targets:

```makefile
api-dev:
	cd api && uvicorn src.app:app --reload --port 8000

worker-dev:
	cd api && celery -A src.workers.celery_app worker --loglevel=info --concurrency=2

test-api:
	cd api && pytest -v --tb=short

test-all:
	cd core && pytest -v --tb=short
	cd api && pytest -v --tb=short
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml docker-compose.dev.yml Makefile api/Dockerfile
git commit -m "chore: add API and worker Docker services, Makefile targets"
```

---

### Task 10: End-to-End Verification

**Files:**
- No new files — verification only

- [ ] **Step 1: Install api package**

Run: `cd api && pip install -e ".[dev]"`
Expected: Installs without errors

- [ ] **Step 2: Run all API tests**

Run: `cd api && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Run all core tests**

Run: `cd core && python -m pytest tests/ -v --tb=short -m "not integration"`
Expected: All unit tests pass

- [ ] **Step 4: Verify API starts**

Run: `cd api && timeout 5 uvicorn src.app:app --port 8000 2>&1 || true`
Expected: `Uvicorn running on http://127.0.0.1:8000` (before timeout kills it)

- [ ] **Step 5: Verify OpenAPI docs generate**

Run (with api running): `curl -s http://localhost:8000/openapi.json | python -m json.tool | head -20`
Expected: Valid JSON with all route paths listed

- [ ] **Step 6: Check route count**

Run: `curl -s http://localhost:8000/openapi.json | python -c "import sys,json; d=json.load(sys.stdin); print(f'{len(d[\"paths\"])} routes')"`
Expected: ~25+ routes (auth + profile + jobs + discovery + search + skills + answers + billing + admin + tasks + health)

- [ ] **Step 7: Run lint**

Run: `ruff check api/src/ api/tests/`
Expected: Clean (no errors)

- [ ] **Step 8: Final commit if any lint fixes needed**

```bash
git add -A && git commit -m "fix(api): lint cleanup"
```

---

## Summary

| Task | What it builds | Files |
|------|---------------|-------|
| 1 | API package scaffold + config | pyproject.toml, config.py, app.py |
| 2 | Dependencies + tenant middleware | deps.py, middleware/tenant.py, conftest.py |
| 3 | Auth (fastapi-users + JWT) | auth/*, schemas.py |
| 4 | Celery workers + task tracking | workers/*, routes/tasks.py |
| 5 | Profile routes | routes/profile.py |
| 6 | Jobs routes | routes/jobs.py |
| 7 | Discovery + search routes | routes/discovery.py, routes/search.py |
| 8 | Skills, answers, billing, admin | routes/skills.py, answers.py, billing.py, admin.py |
| 9 | Docker + Makefile updates | docker-compose.yml, Dockerfile, Makefile |
| 10 | E2E verification | (none — verification only) |
