# Job Application Assistant — Frontend SaaS Platform Design

**Date:** 2026-04-03
**Status:** Approved

## Overview

Transform the existing single-user CLI job application assistant into a multi-tenant SaaS platform. Clients authenticate, manage their professional profiles, scrape/discover/analyze jobs, generate tailored resumes and cover letters, and track skill analytics — all through a web interface.

**Excluded from v1:** Computer use / browser automation for auto-filling applications.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Multi-tenancy | Platform-provided API keys | Frictionless onboarding; migrate to BYOK later |
| Data isolation | PostgreSQL RLS (row-level security) | DB-enforced tenant isolation; industry best practice |
| Backend | FastAPI (Python) | Reuses 100% of existing code |
| Frontend | React/Vite SPA (separate service) | Independent scaling and deployment |
| Auth | fastapi-users + PostgreSQL | Production-quality auth with social login, no external deps |
| File storage | MinIO (S3-compatible) | Pre-signed URLs, portable to any S3 provider |
| Background jobs | Celery + Redis | Proven at scale, rich ecosystem |
| Real-time | Server-Sent Events (SSE) | Server-to-client push via Redis pub/sub |
| Resume input | Form builder + JSON import/export | Accessible UX + power-user escape hatch |
| Repo structure | Modular monorepo (core / api / web) | CLI preserved, clean dependency boundaries |

## Architecture

```
                    ┌─────────────────────────┐
                    │   React/Vite SPA (web/)  │
                    │   shadcn/ui + Tailwind   │
                    │   TanStack Query + Zustand│
                    └───────────┬──────────────┘
                                │ REST + SSE
                    ┌───────────▼──────────────┐
                    │   FastAPI (api/)          │
                    │   Auth · RLS · Rate Limit │
                    │   SSE endpoints           │
                    └──────┬───────────┬────────┘
                           │imports    │enqueues
                 ┌─────────▼──┐  ┌────▼────────┐
                 │ Core (core/)│  │Celery Workers│
                 │ scraper     │  │ scrape_job   │
                 │ analyzer    │  │ analyze_job  │
                 │ generator   │  │ generate_docs│
                 │ llm/models  │  │ discover     │
                 └──────┬──────┘  │ search_*     │
                        │         └──────────────┘
          ┌─────────────┼────────────────┐
    ┌─────▼────┐  ┌─────▼────┐  ┌───────▼──┐  ┌──────────┐
    │PostgreSQL │  │  Redis   │  │  MinIO   │  │External  │
    │ RLS      │  │  broker  │  │  PDFs    │  │APIs      │
    │ users    │  │  pub/sub │  │  S3 API  │  │Anthropic │
    │ jobs     │  │  rates   │  │          │  │Gemini    │
    │ analyses │  │          │  │          │  │Firecrawl │
    └──────────┘  └──────────┘  └──────────┘  └──────────┘
```

**Dependency direction:** `api → core ← cli` — the CLI continues to work standalone.

## Repository Structure

```
job-application-assistant/
├── core/                     # Existing Python code (zero web deps)
│   ├── src/                  # models, scraper, analyzer, generator, db, llm, privacy
│   ├── cli/                  # Click CLI (imports from src/)
│   └── pyproject.toml        # installable as `job-core`
├── api/                      # FastAPI layer (imports core)
│   ├── routes/               # auth, jobs, discovery, search, skills, answers, billing, admin
│   ├── middleware/            # auth, tenant context, rate limiting
│   ├── workers/              # Celery task definitions
│   ├── alembic/              # PostgreSQL migrations
│   └── pyproject.toml        # depends on `job-core`
├── web/                      # React/Vite frontend
│   ├── src/
│   │   ├── components/       # shadcn/ui based components
│   │   ├── pages/            # route pages
│   │   ├── api/              # auto-generated TypeScript client from OpenAPI
│   │   └── stores/           # Zustand stores
│   └── package.json
├── docker-compose.yml        # PG + Redis + MinIO + API + Worker + Beat + Frontend
└── Makefile
```

## Database Schema

### Tenant & Auth Tables (new)

```sql
-- tenants
CREATE TABLE tenants (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    slug          TEXT UNIQUE NOT NULL,
    plan          TEXT DEFAULT 'free',        -- 'free', 'pro', 'enterprise'
    api_usage     JSONB DEFAULT '{}',         -- cached summary counters for quick rate limit checks
    rate_limits   JSONB,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now()
);

-- users (managed by fastapi-users)
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    email           TEXT UNIQUE NOT NULL,
    hashed_password TEXT,
    role            TEXT DEFAULT 'member',     -- 'owner', 'admin', 'member'
    is_active       BOOLEAN DEFAULT true,
    is_verified     BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- user_profiles (replaces master_resume.json)
CREATE TABLE user_profiles (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      UUID NOT NULL,
    user_id        UUID NOT NULL REFERENCES users(id),
    full_name      TEXT,
    contact        JSONB,                      -- {email, phone, linkedin, github, ...}
    summary        TEXT,
    experience     JSONB[] DEFAULT '{}',       -- [{company, title, dates, bullets}, ...]
    education      JSONB[] DEFAULT '{}',       -- [{school, degree, dates}, ...]
    skills         TEXT[] DEFAULT '{}',
    certifications TEXT[] DEFAULT '{}',
    projects       JSONB[] DEFAULT '{}',
    raw_json       JSONB,                      -- original imported JSON
    created_at     TIMESTAMPTZ DEFAULT now(),
    updated_at     TIMESTAMPTZ DEFAULT now()
);
```

### Core Data Tables (migrated from SQLite + tenant_id)

```sql
-- All tables get tenant_id + RLS policy. Showing jobs as example:
CREATE TABLE jobs (
    id               SERIAL PRIMARY KEY,
    tenant_id        UUID NOT NULL,
    url              TEXT NOT NULL,
    url_hash         TEXT NOT NULL,
    title            TEXT NOT NULL,
    company          TEXT NOT NULL,
    location         TEXT,
    salary_range     TEXT,
    job_type         TEXT,
    experience_level TEXT,
    description      TEXT,
    requirements     JSONB DEFAULT '[]',
    responsibilities JSONB DEFAULT '[]',
    benefits         JSONB DEFAULT '[]',
    application_url  TEXT,
    date_posted      TEXT,
    raw_markdown     TEXT,
    scraped_at       TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, url_hash)
);

-- analyses
CREATE TABLE analyses (
    id                SERIAL PRIMARY KEY,
    tenant_id         UUID NOT NULL,
    job_id            INTEGER NOT NULL REFERENCES jobs(id),
    fit_score         INTEGER NOT NULL,
    base_score        INTEGER,
    penalties         JSONB DEFAULT '[]',
    fit_reasoning     TEXT,
    matching_skills   JSONB DEFAULT '[]',
    gaps              JSONB DEFAULT '[]',
    keywords          JSONB DEFAULT '[]',
    tailoring_strategy TEXT,
    analyzed_at       TIMESTAMPTZ DEFAULT now()
);

-- applications
CREATE TABLE applications (
    id                SERIAL PRIMARY KEY,
    tenant_id         UUID NOT NULL,
    job_id            INTEGER NOT NULL REFERENCES jobs(id),
    status            TEXT DEFAULT 'discovered',
    resume_path       TEXT,                     -- MinIO object key
    cover_letter_path TEXT,                     -- MinIO object key
    applied_at        TIMESTAMPTZ,
    notes             TEXT,
    updated_at        TIMESTAMPTZ DEFAULT now()
);

-- job_skills
CREATE TABLE job_skills (
    id           SERIAL PRIMARY KEY,
    tenant_id    UUID NOT NULL,
    job_id       INTEGER NOT NULL REFERENCES jobs(id),
    skill        TEXT NOT NULL,
    source       TEXT DEFAULT 'keyword',
    extracted_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, job_id, skill, source)
);

-- answers
CREATE TABLE answers (
    id            SERIAL PRIMARY KEY,
    tenant_id     UUID NOT NULL,
    question      TEXT NOT NULL,
    question_hash TEXT NOT NULL,
    answer        TEXT NOT NULL,
    source        TEXT DEFAULT 'manual',
    category      TEXT,
    times_used    INTEGER DEFAULT 0,
    last_used_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tenant_id, question_hash)
);
```

### Infrastructure Tables (new)

```sql
-- tasks (tracks Celery job status for SSE)
CREATE TABLE tasks (
    id          UUID PRIMARY KEY,              -- matches Celery task ID
    tenant_id   UUID NOT NULL,
    type        TEXT NOT NULL,                 -- 'scrape', 'analyze', 'generate', 'discover'
    status      TEXT DEFAULT 'pending',        -- 'pending', 'running', 'completed', 'failed'
    input       JSONB,
    result      JSONB,
    error       TEXT,
    progress    INTEGER DEFAULT 0,             -- 0-100
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- search_configs (replaces search_config.json)
CREATE TABLE search_configs (
    id          SERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL,
    name        TEXT NOT NULL,
    config_type TEXT NOT NULL,                 -- 'search_query', 'career_page'
    config      JSONB NOT NULL,
    is_active   BOOLEAN DEFAULT true,
    last_run_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- api_usage_log (detailed audit trail; tenants.api_usage is the cached summary for rate limits)
CREATE TABLE api_usage_log (
    id            SERIAL PRIMARY KEY,
    tenant_id     UUID NOT NULL,
    action        TEXT NOT NULL,               -- 'scrape', 'analyze', 'generate', etc.
    tokens_used   INTEGER DEFAULT 0,
    cost_estimate DECIMAL(10,6),
    created_at    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_usage_tenant_date ON api_usage_log(tenant_id, created_at);
```

### RLS Policy (applied to all tenant tables)

```sql
-- Example for jobs table; same pattern for all tenant tables
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON jobs
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- FastAPI middleware sets this per request:
-- SET app.current_tenant = '{tenant_id}';
```

## API Routes

### Auth — `/api/auth`

```
POST   /api/auth/register          — Create account (email + password)
POST   /api/auth/login             — Get JWT access + refresh tokens
POST   /api/auth/logout            — Invalidate refresh token
POST   /api/auth/refresh           — Rotate access token
POST   /api/auth/forgot-password   — Send password reset email
POST   /api/auth/reset-password    — Set new password with reset token
POST   /api/auth/verify            — Email verification
GET    /api/auth/google/authorize  — Google OAuth2 redirect
GET    /api/auth/google/callback   — Google OAuth2 callback
GET    /api/auth/github/authorize  — GitHub OAuth2 redirect
GET    /api/auth/github/callback   — GitHub OAuth2 callback
GET    /api/auth/me                — Current user info
```

### Profile — `/api/profile`

```
GET    /api/profile                — Get current user's profile
PUT    /api/profile                — Update profile (form-based)
POST   /api/profile/import         — Import JSON (master_resume format)
GET    /api/profile/export         — Export as JSON
```

### Jobs — `/api/jobs`

```
POST   /api/jobs/scrape            — Scrape a URL (returns task_id)
GET    /api/jobs                   — List jobs (paginated, filterable, sortable)
GET    /api/jobs/:id               — Get job details
DELETE /api/jobs/:id               — Remove a job
GET    /api/jobs/:id/analysis      — Get analysis for a job
POST   /api/jobs/:id/analyze       — Re-analyze a job (returns task_id)
POST   /api/jobs/:id/generate      — Generate resume + cover letter (returns task_id)
GET    /api/jobs/:id/documents     — List generated docs (pre-signed MinIO URLs)
GET    /api/jobs/ranked            — Get jobs ranked by fit score
```

### Discovery — `/api/discovery`

```
GET    /api/discovery/configs      — List search configs
POST   /api/discovery/configs      — Create a search config
PUT    /api/discovery/configs/:id  — Update a search config
DELETE /api/discovery/configs/:id  — Delete a search config
POST   /api/discovery/run          — Run all active configs (returns task_id)
POST   /api/discovery/search       — Ad-hoc web search (returns task_id)
```

### Search — `/api/search`

```
POST   /api/search/indeed          — Search Indeed (returns task_id)
POST   /api/search/linkedin        — Search LinkedIn (returns task_id)
```

### Skills & Analytics — `/api/skills`

```
GET    /api/skills/top             — Top requested skills across jobs
GET    /api/skills/gaps            — Skill gaps (required but not in profile)
GET    /api/skills/trends          — Skill demand over time
GET    /api/skills/roles           — Skills grouped by role type
GET    /api/skills/calibration     — Score calibration report
```

### Answers — `/api/answers`

```
GET    /api/answers                — List answers (paginated, searchable)
POST   /api/answers                — Add an answer
PUT    /api/answers/:id            — Update an answer
DELETE /api/answers/:id            — Delete an answer
POST   /api/answers/import         — Bulk import from JSON
GET    /api/answers/stats          — Usage statistics
```

### Billing — `/api/billing`

```
GET    /api/billing/plan           — Current plan + limits
GET    /api/billing/usage          — Usage for current billing period
GET    /api/billing/usage/history  — Historical usage (daily/weekly/monthly)
GET    /api/billing/invoices       — Invoice list (stub until Stripe integration)
```

### Tasks & SSE — `/api/tasks`

```
GET    /api/tasks/:id              — Get task status + result
GET    /api/tasks                  — List recent tasks
GET    /api/tasks/stream           — SSE stream (all events for current tenant)

SSE Event Types:
  task:started    {task_id, type}
  task:progress   {task_id, type, progress, message}
  task:completed  {task_id, type, result}
  task:failed     {task_id, type, error}
  job:discovered  {job_id, title, company, fit_score}
```

### Admin — `/api/admin` (owner/admin only)

```
GET    /api/admin/usage            — Tenant API usage summary
GET    /api/admin/users            — List tenant users
POST   /api/admin/users/invite     — Invite a user to tenant
PUT    /api/admin/users/:id/role   — Change user role
DELETE /api/admin/users/:id        — Remove user from tenant
```

## Frontend Pages

| Route | Purpose |
|-------|---------|
| `/login` | Email/password + Google/GitHub OAuth |
| `/register` | Sign up, creates tenant + user |
| `/forgot-password` | Password reset flow |
| `/dashboard` | Overview cards, quick actions (paste URL, run discovery) |
| `/jobs` | Filterable/sortable job table with status badges |
| `/jobs/:id` | Job detail, analysis breakdown, generated docs download |
| `/discover` | Search config manager, "Run All" with live SSE results |
| `/search` | Indeed + LinkedIn search with streaming results |
| `/skills` | Analytics: top skills chart, gaps, trends, role breakdown, calibration |
| `/profile` | Multi-step profile builder + JSON import/export |
| `/answers` | Screening answer manager: CRUD, bulk import, usage stats |
| `/settings` | Account settings, team management (invite/remove, roles) |
| `/billing` | Plan overview, usage meters, billing cycle |
| `/billing/plans` | Plan comparison table, upgrade/downgrade |
| `/billing/history` | Invoice history, receipts |
| `/billing/usage` | Detailed usage breakdown, charts, cost projections |

### Frontend Tech Stack

| Layer | Choice |
|-------|--------|
| UI components | shadcn/ui + Tailwind CSS |
| Data fetching | TanStack Query |
| Routing | React Router v7 |
| Global state | Zustand |
| Forms | React Hook Form + Zod |
| Charts | Recharts |

### App Shell

Collapsible sidebar navigation, top bar with running task indicator and user avatar, main content area. Sidebar sections: Dashboard, Jobs, Discover, Search, Skills, Profile, Answers, Billing, Settings.

## Security

- **JWT tokens:** Access (15min) + refresh (7d) in httpOnly secure cookies. CSRF via SameSite=Lax + double-submit cookie.
- **Tenant isolation:** PostgreSQL RLS on every tenant table. Middleware sets `app.current_tenant` from JWT claims before any query.
- **Rate limiting:** Redis-backed per-tenant. Tiered by plan: free (10 scrapes/day, 20 analyses/day), pro (100/200), enterprise (custom). 429 with Retry-After header.
- **Input validation:** Pydantic on all API inputs. URL validation (http/https only, no internal IPs). Zod on frontend forms.
- **PII protection:** Existing PIIGuard wraps all LLM calls. Sensitive profile fields encrypted at rest (pgcrypto).
- **CORS:** Whitelist frontend origin only. Credentials mode for cookies. No wildcard origins.

## Error Handling

- **API errors:** Consistent JSON: `{detail, code, field?}`. Standard HTTP status codes (400, 401, 403, 404, 429, 500).
- **Task failures:** Celery retries 3x with exponential backoff. Failed tasks emit `task:failed` SSE event with user-friendly error. Full traceback logged server-side.
- **External API failures:** LLM router fallback (Gemini → Anthropic). Firecrawl failures return partial results. Scraper errors don't crash discovery batch.
- **Frontend:** TanStack Query error boundaries per page. Toast notifications for task failures. Retry buttons. Offline indicator.

## Deployment

### Docker Compose Services

| Service | Image | Port |
|---------|-------|------|
| api | FastAPI (uvicorn) | 8000 |
| worker | Celery worker (concurrency=4) | — |
| beat | Celery beat (scheduled tasks) | — |
| web | React/Vite (nginx) | 3000 |
| postgres | PostgreSQL 16 | 5432 |
| redis | Redis 7 | 6379 |
| minio | MinIO | 9000/9001 |

### Environments

- **Local dev:** `docker-compose up` — hot reload on API (uvicorn --reload) and frontend (vite dev). Alembic migrations auto-run.
- **Production:** Production overrides: gunicorn + uvicorn workers, nginx serves built frontend, SSL via reverse proxy (Caddy/Traefik), secrets from env vars.

## Testing Strategy

- **Backend:** pytest — existing tests migrate. API route tests with httpx TestClient. Celery tasks tested with eager mode. RLS tests verify tenant isolation.
- **Frontend:** Vitest + React Testing Library. MSW for API mocking. Playwright for critical E2E flows (login, scrape, generate).
- **Integration:** Docker-based: spin up PG + Redis, run API tests against real DB with RLS. Verify tenant isolation end-to-end.

## MVP Feature Set

1. Auth — register, login, password reset, social login (Google/GitHub)
2. Profile builder — form-based + JSON import/export
3. Job scraping — paste URL → scrape → extract (Firecrawl)
4. Job discovery — configure searches, crawl career pages, batch discover
5. Job analysis — LLM-powered fit scoring against user profile
6. Resume/cover letter generation — tailored PDFs, downloadable from MinIO
7. Job dashboard — list, rank, filter, view details + analysis
8. Skill analytics — top skills, gaps, trends, role breakdown
9. Answer cache — manage screening answers
10. Indeed search — search via Playwright
11. LinkedIn search/scrape — search via Playwright
12. Billing — usage tracking, plan display (Stripe deferred to monetization phase)

## Future Phases

- **BYOK (Bring Your Own Keys):** Clients provide their own API keys for heavy usage
- **Stripe integration:** Payment processing, automatic plan management
- **Computer use:** Browser automation for auto-filling applications (excluded from v1)
- **Telegram integration:** Per-tenant bot notifications
