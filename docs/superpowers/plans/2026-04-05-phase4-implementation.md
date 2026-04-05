# Phase 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Telegram bot integration, global task panel, refresh token authentication, mobile responsive layout, and comprehensive E2E tests to the Job Application Assistant SaaS platform.

**Architecture:** Telegram bot runs as webhook handlers inside the existing FastAPI app. Notification service dispatches task events to both SSE (web) and Telegram. Refresh tokens use httpOnly cookies with rotation. Frontend gets a slide-out task drawer, bottom mobile nav, and responsive layout adjustments.

**Tech Stack:** FastAPI, python-telegram-bot, Celery, Redis pub/sub, React 19, Zustand, TanStack Query, Tailwind CSS, Playwright

---

## File Structure

### Backend (New files)

| File | Responsibility |
|------|---------------|
| `alembic/versions/002_phase4_telegram_and_tasks.py` | Migration: 3 new tables + tasks.user_id |
| `core/src/db/models.py` | Add TelegramAccount, TelegramLinkCode, NotificationPreference models + Task.user_id |
| `api/src/config.py` | Add telegram_bot_token, telegram_webhook_base_url, cookie_secure settings |
| `api/src/schemas.py` | Add Telegram + notification schemas |
| `api/src/telegram/__init__.py` | Package init |
| `api/src/telegram/webhook.py` | FastAPI router: webhook endpoint + link-code + status + unlink |
| `api/src/telegram/handlers.py` | Command handlers: /jobs, /top, /job, /discover, /search, /generate, /approve, /status, /help |
| `api/src/telegram/linking.py` | Account linking: generate code, verify /start deep link |
| `api/src/telegram/sender.py` | Outbound: send_text, send_document, send_inline_keyboard |
| `api/src/notifications/__init__.py` | Package init |
| `api/src/notifications/dispatcher.py` | notify() — check prefs, dispatch to Telegram |
| `api/src/notifications/formatters.py` | Format task events into Telegram messages |
| `api/src/routes/notifications.py` | GET/PUT /api/notifications/preferences |
| `api/src/auth/refresh.py` | POST /api/auth/refresh endpoint |

### Backend (Modified files)

| File | Changes |
|------|---------|
| `api/src/app.py` | Register telegram, notification routes; refresh backend; webhook setup in lifespan |
| `api/src/auth/backend.py` | Add refresh_backend with CookieTransport |
| `api/src/workers/tasks.py` | Add user_id param to tasks; call notify() after events |
| `api/src/routes/jobs.py` | Pass user.id when creating tasks |
| `api/src/routes/discovery.py` | Pass user.id when creating tasks |
| `api/pyproject.toml` | Add python-telegram-bot dependency |
| `docker-compose.yml` | Add TELEGRAM env vars |

### Frontend (New files)

| File | Responsibility |
|------|---------------|
| `web/src/components/layout/task-badge.tsx` | Activity icon with count badge on icon rail |
| `web/src/components/layout/task-drawer.tsx` | Slide-out panel: running + recent tasks |
| `web/src/components/layout/mobile-nav.tsx` | Bottom tab bar for mobile |

### Frontend (Modified files)

| File | Changes |
|------|---------|
| `web/src/stores/task-store.ts` | Add recentTasks, drawerOpen, completeTask, failTask |
| `web/src/stores/auth-store.ts` | Add isLoading for silent refresh |
| `web/src/hooks/use-task-stream.ts` | Move completed tasks to recentTasks; hydrate on reconnect |
| `web/src/hooks/use-auth.ts` | Add useRefreshToken, useSilentRestore hooks |
| `web/src/api/client.ts` | Add refresh interceptor with queue |
| `web/src/lib/query-keys.ts` | Add telegram, notifications keys |
| `web/src/pages/settings.tsx` | Add TelegramSection + NotificationSection |
| `web/src/components/layout/app-shell.tsx` | Add MobileNav, update layout for responsive |
| `web/src/components/layout/icon-rail.tsx` | Add TaskBadge, hide on mobile |
| `web/src/components/layout/top-bar.tsx` | Show TaskBadge on mobile |
| `web/src/router.tsx` | Add AuthGate wrapper for silent restore |
| `web/src/pages/dashboard.tsx` | Responsive grid |
| `web/src/pages/jobs/detail.tsx` | Single column on mobile |
| `web/src/pages/jobs/list.tsx` | Responsive adjustments |
| `web/src/pages/discover.tsx` | Single column on mobile |
| `web/src/pages/billing/plans.tsx` | Vertical stack on mobile |
| `web/src/pages/settings.tsx` | Full-width cards on mobile |

### E2E Tests (New)

| File | Responsibility |
|------|---------------|
| `e2e/package.json` | Playwright + dependencies |
| `e2e/playwright.config.ts` | Config: 3 browser projects |
| `e2e/fixtures/auth.ts` | Register + login helper |
| `e2e/fixtures/seed.ts` | Create test data via API |
| `e2e/fixtures/telegram-mock.ts` | Mock Telegram Bot API |
| `e2e/tests/*.spec.ts` | 13 test suite files |

---

### Task 1: Database Migration — New Tables + Task.user_id

**Files:**
- Modify: `core/src/db/models.py`
- Create: `alembic/versions/002_phase4_telegram_and_tasks.py`
- Test: `api/tests/test_migration_002.py`

- [ ] **Step 1: Add new ORM models to core/src/db/models.py**

Add after the existing `ApiUsageLog` class at the end of the file:

```python
class TelegramAccount(Base):
    __tablename__ = "telegram_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    chat_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class TelegramLinkCode(Base):
    __tablename__ = "telegram_link_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
```

Also add `user_id` to the existing `Task` class (after `tenant_id`):

```python
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
```

Also add `BigInteger` to the imports from sqlalchemy (for `chat_id`). Replace `Integer` usage for `chat_id` with `BigInteger`:

```python
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
```

And use `BigInteger` for `chat_id`:

```python
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
```

- [ ] **Step 2: Create the Alembic migration**

Create `alembic/versions/002_phase4_telegram_and_tasks.py`:

```python
"""Phase 4: Telegram accounts, link codes, notification prefs, task user_id.

Revision ID: 002
Revises: 001
Create Date: 2026-04-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_RLS_TABLES = ["telegram_accounts", "notification_preferences"]


def upgrade() -> None:
    # --- telegram_accounts ---
    op.create_table(
        "telegram_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("chat_id", sa.BigInteger, unique=True, nullable=False),
        sa.Column("username", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # --- telegram_link_codes (no RLS) ---
    op.create_table(
        "telegram_link_codes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("code", sa.Text, unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )

    # --- notification_preferences ---
    op.create_table(
        "notification_preferences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column("telegram_enabled", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # --- Add user_id to tasks ---
    op.add_column("tasks", sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True))

    # --- Grant privileges to API role ---
    for table in ["telegram_accounts", "telegram_link_codes", "notification_preferences"]:
        op.execute(f"GRANT ALL PRIVILEGES ON {table} TO jobapp_api")

    # --- RLS on new tenant-scoped tables ---
    for table in NEW_RLS_TABLES:
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
    for table in reversed(NEW_RLS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_insert ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_column("tasks", "user_id")
    op.drop_table("notification_preferences")
    op.drop_table("telegram_link_codes")
    op.drop_table("telegram_accounts")
```

- [ ] **Step 3: Write test for migration models**

Create `api/tests/test_migration_002.py`:

```python
"""Verify Phase 4 ORM models are importable and have correct columns."""

from src.db.models import NotificationPreference, TelegramAccount, TelegramLinkCode, Task


def test_telegram_account_columns():
    cols = {c.name for c in TelegramAccount.__table__.columns}
    assert {"id", "tenant_id", "user_id", "chat_id", "username", "is_active", "linked_at"} <= cols


def test_telegram_link_code_columns():
    cols = {c.name for c in TelegramLinkCode.__table__.columns}
    assert {"id", "user_id", "code", "expires_at"} <= cols


def test_notification_preference_columns():
    cols = {c.name for c in NotificationPreference.__table__.columns}
    assert {"id", "tenant_id", "user_id", "telegram_enabled"} <= cols


def test_task_has_user_id():
    cols = {c.name for c in Task.__table__.columns}
    assert "user_id" in cols
```

- [ ] **Step 4: Run tests**

Run: `cd api && python -m pytest tests/test_migration_002.py -v`
Expected: 4 PASS

- [ ] **Step 5: Run migration against Docker DB**

```bash
DATABASE_URL=postgresql://jobapp:jobapp_dev@localhost:5432/jobapp alembic upgrade head
```

Verify tables exist:

```bash
docker compose exec postgres psql -U jobapp -d jobapp -c "\dt telegram*" -c "\dt notification*" -c "\d tasks"
```

- [ ] **Step 6: Commit**

```bash
git add core/src/db/models.py alembic/versions/002_phase4_telegram_and_tasks.py api/tests/test_migration_002.py
git commit -m "feat: add Phase 4 migration — telegram_accounts, link_codes, notification_preferences, tasks.user_id"
```

---

### Task 2: Config + Schemas for Telegram and Notifications

**Files:**
- Modify: `api/src/config.py`
- Modify: `api/src/schemas.py`
- Modify: `api/src/lib/query-keys.ts`

- [ ] **Step 1: Add Telegram and cookie settings to config**

Add to `api/src/config.py` Settings class, after the MinIO fields:

```python
    # Telegram
    telegram_bot_token: str = ""
    telegram_webhook_base_url: str = ""

    # Cookie security (False for local HTTP dev)
    cookie_secure: bool = False
```

- [ ] **Step 2: Add Telegram and notification schemas**

Add to `api/src/schemas.py` after the `SkillGap` class:

```python
# --- Telegram schemas ---

class TelegramLinkCodeResponse(BaseModel):
    code: str
    deep_link: str


class TelegramStatusResponse(BaseModel):
    linked: bool
    username: str | None = None
    chat_id: int | None = None
    is_active: bool = False


# --- Notification schemas ---

class NotificationPreferencesRead(BaseModel):
    telegram_enabled: bool = True

    model_config = {"from_attributes": True}


class NotificationPreferencesUpdate(BaseModel):
    telegram_enabled: bool
```

- [ ] **Step 3: Add query keys for frontend**

Add to `web/src/lib/query-keys.ts` after the `admin` key:

```typescript
  telegram: {
    status: ["telegram", "status"] as const,
  },
  notifications: {
    preferences: ["notifications", "preferences"] as const,
  },
```

- [ ] **Step 4: Run existing tests to ensure nothing breaks**

Run: `cd api && python -m pytest tests/ -v --tb=short`
Expected: All existing tests PASS

- [ ] **Step 5: Commit**

```bash
git add api/src/config.py api/src/schemas.py web/src/lib/query-keys.ts
git commit -m "feat: add Telegram and notification config, schemas, query keys"
```

---

### Task 3: Refresh Token Backend

**Files:**
- Modify: `api/src/auth/backend.py`
- Create: `api/src/auth/refresh.py`
- Modify: `api/src/app.py`
- Test: `api/tests/test_refresh.py`

- [ ] **Step 1: Write failing test**

Create `api/tests/test_refresh.py`:

```python
"""Test refresh token endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_refresh_endpoint_exists(client):
    resp = await client.post("/api/auth/refresh")
    # Should return 401 (no cookie), not 404 (missing route)
    assert resp.status_code != 404


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(client):
    resp = await client.post("/api/auth/refresh")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_refresh.py -v`
Expected: FAIL — 404 Not Found (endpoint doesn't exist yet)

- [ ] **Step 3: Add refresh backend to auth/backend.py**

Replace the full content of `api/src/auth/backend.py`:

```python
"""JWT authentication backend for fastapi-users — access + refresh tokens."""

import uuid

from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    CookieTransport,
    JWTStrategy,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.manager import UserManager
from src.auth.models import get_user_db
from src.config import settings
from src.db.models import User
from src.deps import get_db_session

# --- Access token (Bearer header, 15 min) ---
bearer_transport = BearerTransport(tokenUrl="/api/auth/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=settings.jwt_secret, lifetime_seconds=settings.jwt_lifetime_seconds)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# --- Refresh token (httpOnly cookie, 7 days) ---
cookie_transport = CookieTransport(
    cookie_name="refresh_token",
    cookie_httponly=True,
    cookie_secure=settings.cookie_secure,
    cookie_samesite="lax",
    cookie_max_age=settings.jwt_refresh_lifetime_seconds,
)


def get_refresh_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.jwt_secret,
        lifetime_seconds=settings.jwt_refresh_lifetime_seconds,
        token_audience=["fastapi-users:refresh"],
    )


refresh_backend = AuthenticationBackend(
    name="jwt-refresh",
    transport=cookie_transport,
    get_strategy=get_refresh_strategy,
)


# --- User manager dependency ---
async def get_user_manager(session: AsyncSession = Depends(get_db_session)):
    user_db = get_user_db(session)
    db = await user_db.__anext__()
    yield UserManager(db)


# --- FastAPI Users instance ---
fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend, refresh_backend])

current_active_user = fastapi_users.current_user(active=True)
```

- [ ] **Step 4: Create refresh endpoint**

Create `api/src/auth/refresh.py`:

```python
"""Refresh token endpoint — exchange refresh cookie for new access token."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi_users.authentication import JWTStrategy

from src.auth.backend import get_jwt_strategy, get_refresh_strategy, get_user_manager
from src.auth.manager import UserManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    user_manager: UserManager = Depends(get_user_manager),
):
    """Read refresh_token cookie, validate, return new access + refresh tokens."""
    refresh_cookie = request.cookies.get("refresh_token")
    if not refresh_cookie:
        raise HTTPException(status_code=401, detail="No refresh token")

    # Validate refresh token
    refresh_strategy: JWTStrategy = get_refresh_strategy()
    user = await refresh_strategy.read_token(refresh_cookie, user_manager)
    if user is None or not user.is_active:
        # Clear invalid cookie
        response.delete_cookie("refresh_token", path="/api/auth")
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Generate new access token
    access_strategy: JWTStrategy = get_jwt_strategy()
    access_token = await access_strategy.write_token(user)

    # Generate new refresh token (rotation)
    new_refresh = await refresh_strategy.write_token(user)
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=604800,
        path="/api/auth",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "role": user.role,
        },
    }
```

- [ ] **Step 5: Register refresh route and set refresh cookie on login**

In `api/src/app.py`, add the import and route registration. After the existing verify router include:

```python
    from src.auth.refresh import router as refresh_router
    app.include_router(refresh_router)
```

Also add the refresh auth router for login (sets refresh cookie):

```python
    app.include_router(
        fastapi_users.get_auth_router(refresh_backend),
        prefix="/api/auth/refresh-login",
        tags=["auth"],
    )
```

Update the login router to use BOTH backends — the existing login endpoint returns access token in body. We need to add a custom login endpoint that also sets the refresh cookie. Replace the existing login router block:

Add after the existing auth routes, before the API routes section:

```python
    # Custom login that sets both access token (body) and refresh token (cookie)
    @app.post("/api/auth/login", tags=["auth"])
    async def custom_login(request: Request, response: Response):
        from fastapi_users.authentication import JWTStrategy
        from src.auth.backend import get_jwt_strategy, get_refresh_strategy, get_user_manager
        from src.deps import get_db_session

        # Parse form data
        form = await request.form()
        email = form.get("username", "")
        password = form.get("password", "")

        # Get user manager
        factory = get_session_factory()
        async with factory() as session:
            from src.auth.models import get_user_db
            user_db_gen = get_user_db(session)
            user_db = await user_db_gen.__anext__()
            manager = UserManager(user_db)

            # Authenticate
            user = await manager.authenticate(
                fastapi_users_models.UserCreate(email=email, password=password)
            )
            ...
```

Actually, this approach is too complex. A simpler approach: keep the existing login as-is (returns access token), and add a response hook that sets the refresh cookie. The cleanest way with fastapi-users is to override the login route.

Let me simplify. Instead of overriding login, we make the refresh endpoint the primary session mechanism. The login flow becomes:

1. `POST /api/auth/login` → returns `{access_token}` (existing, unchanged)
2. `POST /api/auth/refresh-login` → returns refresh cookie (new, called immediately after login by frontend)
3. `POST /api/auth/refresh` → exchange refresh cookie for new access token

Actually even simpler: just include the refresh backend's auth router which gives us `POST /api/auth/refresh-login/login` that returns the refresh cookie. The frontend calls BOTH endpoints.

Let me use the simplest approach. In `api/src/app.py`, add:

```python
    # Refresh token login (sets httpOnly cookie)
    app.include_router(
        fastapi_users.get_auth_router(refresh_backend),
        prefix="/api/auth/cookie",
        tags=["auth"],
    )

    # Refresh endpoint
    from src.auth.refresh import router as refresh_router
    app.include_router(refresh_router)
```

The frontend will call:
1. `POST /api/auth/login` (existing) → get access_token
2. `POST /api/auth/cookie/login` (new) → set refresh cookie
3. `POST /api/auth/refresh` → exchange cookie for new access token on page reload

Both login calls use the same form-encoded username/password.

- [ ] **Step 6: Update app.py with refresh routes**

Add these imports at the top of `api/src/app.py`:

```python
from src.auth.backend import auth_backend, refresh_backend, fastapi_users
```

(Replace the existing `from src.auth.backend import auth_backend, fastapi_users` line.)

Add after the verify router:

```python
    app.include_router(
        fastapi_users.get_auth_router(refresh_backend),
        prefix="/api/auth/cookie",
        tags=["auth"],
    )
    from src.auth.refresh import router as refresh_router
    app.include_router(refresh_router)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd api && python -m pytest tests/test_refresh.py -v`
Expected: 2 PASS

- [ ] **Step 8: Commit**

```bash
git add api/src/auth/backend.py api/src/auth/refresh.py api/src/app.py api/tests/test_refresh.py
git commit -m "feat: add refresh token backend — cookie transport, /api/auth/refresh endpoint"
```

---

### Task 4: Refresh Token Frontend

**Files:**
- Modify: `web/src/api/client.ts`
- Modify: `web/src/hooks/use-auth.ts`
- Modify: `web/src/stores/auth-store.ts`
- Modify: `web/src/router.tsx`
- Modify: `web/src/hooks/use-task-stream.ts`

- [ ] **Step 1: Update auth store — add isLoading state**

Replace `web/src/stores/auth-store.ts`:

```typescript
import { create } from "zustand";

interface AuthUser {
  id: string;
  email: string;
  tenant_id: string;
  role: string;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setAuth: (token: string, user: AuthUser) => void;
  setLoading: (loading: boolean) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  isAuthenticated: false,
  isLoading: true,
  setAuth: (token, user) => set({ token, user, isAuthenticated: true, isLoading: false }),
  setLoading: (isLoading) => set({ isLoading }),
  logout: () => set({ token: null, user: null, isAuthenticated: false, isLoading: false }),
}));
```

- [ ] **Step 2: Update Axios interceptor — add refresh logic**

Replace `web/src/api/client.ts`:

```typescript
import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/stores/auth-store";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "",
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let isRefreshing = false;
let pendingRequests: Array<{
  resolve: (config: InternalAxiosRequestConfig) => void;
  reject: (error: unknown) => void;
}> = [];

function processPendingRequests(token: string | null) {
  pendingRequests.forEach(({ resolve, reject }) => {
    if (token) {
      resolve({ headers: { Authorization: `Bearer ${token}` } } as InternalAxiosRequestConfig);
    } else {
      reject(new Error("Refresh failed"));
    }
  });
  pendingRequests = [];
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config;
    if (!originalRequest || error.response?.status !== 401) {
      return Promise.reject(error);
    }

    // Don't retry refresh or login endpoints
    const url = originalRequest.url || "";
    if (url.includes("/auth/refresh") || url.includes("/auth/login")) {
      useAuthStore.getState().logout();
      window.location.href = "/login";
      return Promise.reject(error);
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        pendingRequests.push({ resolve, reject });
      }).then((config) => apiClient(Object.assign({}, originalRequest, config)));
    }

    isRefreshing = true;
    try {
      const resp = await axios.post(
        `${import.meta.env.VITE_API_URL || ""}/api/auth/refresh`,
        null,
        { withCredentials: true },
      );
      const { access_token, user } = resp.data;
      useAuthStore.getState().setAuth(access_token, user);
      processPendingRequests(access_token);
      originalRequest.headers.Authorization = `Bearer ${access_token}`;
      return apiClient(originalRequest);
    } catch {
      processPendingRequests(null);
      useAuthStore.getState().logout();
      window.location.href = "/login";
      return Promise.reject(error);
    } finally {
      isRefreshing = false;
    }
  },
);

export { apiClient };
```

- [ ] **Step 3: Update use-auth.ts — dual login + silent restore**

Replace `web/src/hooks/use-auth.ts`:

```typescript
import { useMutation } from "@tanstack/react-query";
import axios from "axios";
import { apiClient } from "@/api/client";
import { useAuthStore } from "@/stores/auth-store";

interface LoginCredentials {
  email: string;
  password: string;
}

interface RegisterData {
  email: string;
  password: string;
}

export function useLogin() {
  const setAuth = useAuthStore((s) => s.setAuth);

  return useMutation({
    mutationFn: async (creds: LoginCredentials) => {
      const form = new URLSearchParams();
      form.append("username", creds.email);
      form.append("password", creds.password);

      // 1. Get access token
      const resp = await apiClient.post("/api/auth/login", form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      const token = resp.data.access_token;

      // 2. Set refresh cookie (same credentials, cookie endpoint)
      await axios.post(
        `${import.meta.env.VITE_API_URL || ""}/api/auth/cookie/login`,
        form,
        {
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          withCredentials: true,
        },
      );

      // 3. Set temp auth so /users/me works
      useAuthStore.getState().setAuth(token, { id: "", email: creds.email, tenant_id: "", role: "" });

      // 4. Fetch full user details
      const userResp = await apiClient.get("/api/users/me");
      const user = userResp.data;
      setAuth(token, {
        id: user.id,
        email: user.email,
        tenant_id: user.tenant_id,
        role: user.role || "member",
      });

      return user;
    },
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: async (data: RegisterData) => {
      const resp = await apiClient.post("/api/auth/register", {
        email: data.email,
        password: data.password,
      });
      return resp.data;
    },
  });
}

export function useForgotPassword() {
  return useMutation({
    mutationFn: async (email: string) => {
      await apiClient.post("/api/auth/forgot-password", { email });
    },
  });
}

export function useLogout() {
  const logout = useAuthStore((s) => s.logout);

  return useMutation({
    mutationFn: async () => {
      try {
        await apiClient.post("/api/auth/logout");
        // Also clear refresh cookie
        await axios.post(
          `${import.meta.env.VITE_API_URL || ""}/api/auth/cookie/logout`,
          null,
          { withCredentials: true },
        );
      } catch {
        // Logout even if API call fails
      }
      logout();
    },
  });
}

/**
 * Attempt silent restore on app mount using refresh cookie.
 * Returns true if session was restored, false otherwise.
 */
export async function silentRestore(): Promise<boolean> {
  try {
    const resp = await axios.post(
      `${import.meta.env.VITE_API_URL || ""}/api/auth/refresh`,
      null,
      { withCredentials: true },
    );
    const { access_token, user } = resp.data;
    useAuthStore.getState().setAuth(access_token, user);
    return true;
  } catch {
    useAuthStore.getState().setLoading(false);
    return false;
  }
}
```

- [ ] **Step 4: Update router.tsx — add silent restore on app mount**

Replace `web/src/router.tsx`:

```typescript
import { createBrowserRouter, Navigate, redirect } from "react-router";
import { AppShell } from "@/components/layout/app-shell";
import { ErrorBoundary } from "@/components/shared/error-boundary";
import { useAuthStore } from "@/stores/auth-store";
import { silentRestore } from "@/hooks/use-auth";
import LoginPage from "@/pages/auth/login";
import RegisterPage from "@/pages/auth/register";
import ForgotPasswordPage from "@/pages/auth/forgot-password";

let restoreAttempted = false;

async function requireAuth() {
  // On first load, attempt silent restore from refresh cookie
  if (!restoreAttempted) {
    restoreAttempted = true;
    await silentRestore();
  }
  if (!useAuthStore.getState().isAuthenticated) return redirect("/login");
  return null;
}

function requireGuest() {
  if (useAuthStore.getState().isAuthenticated) return redirect("/dashboard");
  return null;
}

export const router = createBrowserRouter([
  { path: "/login", loader: requireGuest, element: <LoginPage /> },
  { path: "/register", loader: requireGuest, element: <RegisterPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  {
    path: "/",
    loader: requireAuth,
    element: <AppShell />,
    errorElement: <ErrorBoundary><div>Route error</div></ErrorBoundary>,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", lazy: () => import("@/pages/dashboard") },
      { path: "jobs", lazy: () => import("@/pages/jobs/list") },
      { path: "jobs/:id", lazy: () => import("@/pages/jobs/detail") },
      { path: "profile", lazy: () => import("@/pages/profile") },
      { path: "discover", lazy: () => import("@/pages/discover") },
      { path: "search", lazy: () => import("@/pages/search") },
      { path: "skills", lazy: () => import("@/pages/skills") },
      { path: "answers", lazy: () => import("@/pages/answers") },
      { path: "settings", lazy: () => import("@/pages/settings") },
      { path: "billing", lazy: () => import("@/pages/billing/overview") },
      { path: "billing/plans", lazy: () => import("@/pages/billing/plans") },
      { path: "billing/usage", lazy: () => import("@/pages/billing/usage") },
      { path: "billing/history", lazy: () => import("@/pages/billing/history") },
    ],
  },
  { path: "*", element: <Navigate to="/dashboard" replace /> },
]);
```

- [ ] **Step 5: Update use-task-stream.ts — reconnect on token change**

The existing hook already has `token` in its dependency array, so when the token changes (after refresh), the effect cleanup runs and reconnects with the new token. No changes needed — verify the dependency array includes `token`:

```typescript
  }, [isAuthenticated, token, addTask, updateTask, removeTask, queryClient]);
```

This is already correct. No changes needed.

- [ ] **Step 6: Build frontend to verify TypeScript**

Run: `cd web && npx tsc --noEmit`
Expected: 0 errors

- [ ] **Step 7: Commit**

```bash
git add web/src/stores/auth-store.ts web/src/api/client.ts web/src/hooks/use-auth.ts web/src/router.tsx
git commit -m "feat: add refresh token frontend — silent restore, Axios interceptor with retry queue"
```

---

### Task 5: Telegram Bot — Sender + Linking

**Files:**
- Create: `api/src/telegram/__init__.py`
- Create: `api/src/telegram/sender.py`
- Create: `api/src/telegram/linking.py`
- Modify: `api/pyproject.toml`
- Test: `api/tests/test_telegram_linking.py`

- [ ] **Step 1: Add python-telegram-bot dependency**

In `api/pyproject.toml`, add to dependencies list:

```
    "python-telegram-bot>=21.0",
```

- [ ] **Step 2: Create telegram package init**

Create `api/src/telegram/__init__.py`:

```python
```

(Empty file — package marker.)

- [ ] **Step 3: Create sender.py — outbound Telegram messages**

Create `api/src/telegram/sender.py`:

```python
"""Outbound Telegram messages — text, inline keyboards, documents."""

import logging

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config import settings

logger = logging.getLogger(__name__)

_bot: telegram.Bot | None = None


def get_bot() -> telegram.Bot | None:
    """Lazy-init the Telegram bot. Returns None if token not configured."""
    global _bot
    if not settings.telegram_bot_token:
        return None
    if _bot is None:
        _bot = telegram.Bot(token=settings.telegram_bot_token)
    return _bot


async def send_text(chat_id: int, text: str, parse_mode: str = "Markdown") -> None:
    """Send a text message to a Telegram chat."""
    bot = get_bot()
    if not bot:
        return
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
    except Exception:
        logger.exception("Failed to send Telegram message to chat_id=%s", chat_id)


async def send_inline_keyboard(
    chat_id: int,
    text: str,
    buttons: list[list[tuple[str, str]]],
    parse_mode: str = "Markdown",
) -> None:
    """Send a message with inline keyboard buttons.

    buttons: list of rows, each row is a list of (label, callback_data) tuples.
    """
    bot = get_bot()
    if not bot:
        return
    keyboard = [
        [InlineKeyboardButton(label, callback_data=data) for label, data in row]
        for row in buttons
    ]
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception:
        logger.exception("Failed to send Telegram keyboard to chat_id=%s", chat_id)


async def send_document(chat_id: int, document: bytes, filename: str, caption: str = "") -> None:
    """Send a file (e.g., PDF) to a Telegram chat."""
    bot = get_bot()
    if not bot:
        return
    try:
        await bot.send_document(
            chat_id=chat_id,
            document=document,
            filename=filename,
            caption=caption,
        )
    except Exception:
        logger.exception("Failed to send Telegram document to chat_id=%s", chat_id)
```

- [ ] **Step 4: Create linking.py — account linking logic**

Create `api/src/telegram/linking.py`:

```python
"""Telegram account linking — code generation and verification."""

import logging
import secrets
from datetime import datetime, timezone, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models import NotificationPreference, TelegramAccount, TelegramLinkCode, User

logger = logging.getLogger(__name__)

LINK_CODE_LENGTH = 12
LINK_CODE_TTL_MINUTES = 10


async def generate_link_code(session: AsyncSession, user_id: str) -> dict:
    """Generate a one-time link code for Telegram account linking."""
    import uuid

    # Delete any existing codes for this user
    await session.execute(
        delete(TelegramLinkCode).where(TelegramLinkCode.user_id == uuid.UUID(user_id))
    )

    code = secrets.token_urlsafe(LINK_CODE_LENGTH)[:LINK_CODE_LENGTH]
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=LINK_CODE_TTL_MINUTES)

    link_code = TelegramLinkCode(
        user_id=uuid.UUID(user_id),
        code=code,
        expires_at=expires_at,
    )
    session.add(link_code)
    await session.commit()

    # Build deep link
    bot_username = ""
    if settings.telegram_bot_token:
        from src.telegram.sender import get_bot
        bot = get_bot()
        if bot:
            try:
                me = await bot.get_me()
                bot_username = me.username
            except Exception:
                logger.warning("Could not fetch bot username")

    deep_link = f"https://t.me/{bot_username}?start={code}" if bot_username else ""

    return {"code": code, "deep_link": deep_link}


async def verify_link_code(
    session: AsyncSession, code: str, chat_id: int, username: str | None,
) -> tuple[bool, str]:
    """Verify a link code from /start command. Returns (success, message)."""
    import uuid

    # Look up the code
    result = await session.execute(
        select(TelegramLinkCode).where(TelegramLinkCode.code == code)
    )
    link_code = result.scalar_one_or_none()

    if not link_code:
        return False, "Invalid or expired code. Please try again from Settings."

    if link_code.expires_at < datetime.now(timezone.utc):
        await session.delete(link_code)
        await session.commit()
        return False, "Code expired. Please generate a new one from Settings."

    # Get user to find tenant_id
    user_result = await session.execute(
        select(User).where(User.id == link_code.user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        return False, "User not found."

    # Check if chat_id already linked to another account
    existing = await session.execute(
        select(TelegramAccount).where(TelegramAccount.chat_id == chat_id)
    )
    if existing.scalar_one_or_none():
        await session.delete(link_code)
        await session.commit()
        return False, "This Telegram account is already linked to another user."

    # Create telegram account
    telegram_account = TelegramAccount(
        tenant_id=user.tenant_id,
        user_id=user.id,
        chat_id=chat_id,
        username=username,
    )
    session.add(telegram_account)

    # Create default notification preferences (with tenant context)
    from sqlalchemy import text
    await session.execute(text(f"SET app.current_tenant = '{user.tenant_id}'"))

    existing_prefs = await session.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    if not existing_prefs.scalar_one_or_none():
        prefs = NotificationPreference(
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
        session.add(prefs)

    # Delete the used code
    await session.delete(link_code)
    await session.commit()

    return True, f"Linked to {user.email}! You'll now receive notifications here."


async def get_telegram_status(session: AsyncSession, user_id: str) -> dict:
    """Check if a user has a linked Telegram account."""
    import uuid

    result = await session.execute(
        select(TelegramAccount).where(TelegramAccount.user_id == uuid.UUID(user_id))
    )
    account = result.scalar_one_or_none()
    if account:
        return {
            "linked": True,
            "username": account.username,
            "chat_id": account.chat_id,
            "is_active": account.is_active,
        }
    return {"linked": False, "username": None, "chat_id": None, "is_active": False}


async def unlink_telegram(session: AsyncSession, user_id: str) -> bool:
    """Remove telegram account link."""
    import uuid

    result = await session.execute(
        select(TelegramAccount).where(TelegramAccount.user_id == uuid.UUID(user_id))
    )
    account = result.scalar_one_or_none()
    if account:
        await session.delete(account)
        await session.commit()
        return True
    return False
```

- [ ] **Step 5: Write tests for linking logic**

Create `api/tests/test_telegram_linking.py`:

```python
"""Test Telegram account linking logic."""

from src.db.models import TelegramAccount, TelegramLinkCode, NotificationPreference


def test_telegram_account_model():
    """Verify TelegramAccount model has required fields."""
    cols = {c.name for c in TelegramAccount.__table__.columns}
    assert "chat_id" in cols
    assert "user_id" in cols
    assert "tenant_id" in cols
    assert "is_active" in cols


def test_link_code_model():
    """Verify TelegramLinkCode model has required fields."""
    cols = {c.name for c in TelegramLinkCode.__table__.columns}
    assert "code" in cols
    assert "user_id" in cols
    assert "expires_at" in cols


def test_notification_preference_model():
    """Verify NotificationPreference model has required fields."""
    cols = {c.name for c in NotificationPreference.__table__.columns}
    assert "telegram_enabled" in cols
    assert "user_id" in cols
```

- [ ] **Step 6: Run tests**

Run: `cd api && python -m pytest tests/test_telegram_linking.py -v`
Expected: 3 PASS

- [ ] **Step 7: Commit**

```bash
git add api/pyproject.toml api/src/telegram/ api/tests/test_telegram_linking.py
git commit -m "feat: add Telegram sender, account linking logic, and python-telegram-bot dependency"
```

---

### Task 6: Telegram Webhook Router

**Files:**
- Create: `api/src/telegram/webhook.py`
- Modify: `api/src/app.py`
- Test: `api/tests/test_telegram_webhook.py`

- [ ] **Step 1: Write failing test**

Create `api/tests/test_telegram_webhook.py`:

```python
"""Test Telegram webhook endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from src.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_webhook_endpoint_exists(client):
    resp = await client.post("/api/telegram/webhook/fake-token", json={})
    # Should not be 404
    assert resp.status_code != 404


@pytest.mark.asyncio
async def test_link_code_requires_auth(client):
    resp = await client.post("/api/telegram/link-code")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_status_requires_auth(client):
    resp = await client.get("/api/telegram/status")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unlink_requires_auth(client):
    resp = await client.delete("/api/telegram/unlink")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd api && python -m pytest tests/test_telegram_webhook.py -v`
Expected: FAIL — 404 (routes don't exist)

- [ ] **Step 3: Create webhook router**

Create `api/src/telegram/webhook.py`:

```python
"""Telegram webhook + linking API routes."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.config import settings
from src.db.models import User
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import TelegramLinkCodeResponse, TelegramStatusResponse
from src.telegram.linking import (
    generate_link_code,
    get_telegram_status,
    unlink_telegram,
    verify_link_code,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook/{token}")
async def telegram_webhook(
    token: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Receive Telegram webhook updates."""
    if token != settings.telegram_bot_token:
        raise HTTPException(status_code=403, detail="Invalid token")

    body = await request.json()
    logger.info("Telegram webhook update: %s", json.dumps(body)[:200])

    # Handle /start command for account linking
    message = body.get("message", {})
    text = message.get("text", "")
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    from_user = message.get("from", {})
    username = from_user.get("username")

    if text.startswith("/start ") and chat_id:
        code = text.split(" ", 1)[1].strip()
        success, reply = await verify_link_code(session, code, chat_id, username)
        from src.telegram.sender import send_text
        await send_text(chat_id, reply)
        return {"ok": True}

    # Handle other commands
    if text.startswith("/") and chat_id:
        from src.telegram.handlers import handle_command
        await handle_command(session, chat_id, text, body)
        return {"ok": True}

    # Handle callback queries (inline keyboard buttons)
    callback_query = body.get("callback_query")
    if callback_query:
        cb_chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
        cb_data = callback_query.get("data", "")
        if cb_chat_id:
            from src.telegram.handlers import handle_callback
            await handle_callback(session, cb_chat_id, cb_data)
        return {"ok": True}

    return {"ok": True}


@router.post("/link-code", response_model=TelegramLinkCodeResponse)
async def create_link_code(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Generate a Telegram linking deep link for the current user."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=503, detail="Telegram bot not configured")
    result = await generate_link_code(session, str(user.id))
    return result


@router.get("/status", response_model=TelegramStatusResponse)
async def telegram_status(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Check if the current user has a linked Telegram account."""
    await set_tenant_context(session, str(user.tenant_id))
    return await get_telegram_status(session, str(user.id))


@router.delete("/unlink")
async def telegram_unlink(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    """Disconnect the current user's Telegram account."""
    await set_tenant_context(session, str(user.tenant_id))
    success = await unlink_telegram(session, str(user.id))
    if not success:
        raise HTTPException(status_code=404, detail="No linked Telegram account")
    return {"ok": True}
```

- [ ] **Step 4: Register webhook routes in app.py**

Add to `api/src/app.py` in the `create_app()` function, after the task routes:

```python
    from src.telegram.webhook import router as telegram_router
    app.include_router(telegram_router)
```

Also add webhook setup in the lifespan function. Replace the existing lifespan:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set secrets from settings
    UserManager.reset_password_token_secret = settings.jwt_secret
    UserManager.verification_token_secret = settings.jwt_secret

    # Register Telegram webhook if configured
    if settings.telegram_bot_token and settings.telegram_webhook_base_url:
        try:
            from src.telegram.sender import get_bot
            bot = get_bot()
            if bot:
                webhook_url = f"{settings.telegram_webhook_base_url}/api/telegram/webhook/{settings.telegram_bot_token}"
                await bot.set_webhook(url=webhook_url)
                logger.info("Telegram webhook registered: %s", webhook_url[:50] + "...")
        except Exception:
            logger.exception("Failed to register Telegram webhook")
    else:
        logger.info("Telegram bot disabled — TELEGRAM_BOT_TOKEN or TELEGRAM_WEBHOOK_BASE_URL not set")

    yield
```

Add `import logging` at the top of app.py and `logger = logging.getLogger(__name__)` after imports.

- [ ] **Step 5: Run tests**

Run: `cd api && python -m pytest tests/test_telegram_webhook.py -v`
Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add api/src/telegram/webhook.py api/src/app.py api/tests/test_telegram_webhook.py
git commit -m "feat: add Telegram webhook router — /start linking, command dispatch, link-code, status, unlink"
```

---

### Task 7: Telegram Command Handlers

**Files:**
- Create: `api/src/telegram/handlers.py`
- Test: `api/tests/test_telegram_handlers.py`

- [ ] **Step 1: Create handlers.py**

Create `api/src/telegram/handlers.py`:

```python
"""Telegram command handlers — adapted from core/src/agent/telegram_bot.py for SaaS."""

import logging
import time
import uuid

import redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models import Analysis, Application, Job, TelegramAccount, User
from src.db.models import Task as TaskModel
from src.db.pg import set_tenant_context
from src.telegram.sender import send_inline_keyboard, send_text

logger = logging.getLogger(__name__)

HEAVY_CMD_COOLDOWN = 30  # seconds


def _md_escape(text) -> str:
    """Escape Telegram Markdown special characters."""
    if text is None:
        return "N/A"
    text = str(text)
    for ch in "_*`[":
        text = text.replace(ch, f"\\{ch}")
    return text


async def _get_user_for_chat(session: AsyncSession, chat_id: int) -> tuple[TelegramAccount | None, User | None]:
    """Look up linked Telegram account and user by chat_id."""
    result = await session.execute(
        select(TelegramAccount).where(TelegramAccount.chat_id == chat_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        return None, None
    user_result = await session.execute(select(User).where(User.id == account.user_id))
    user = user_result.scalar_one_or_none()
    return account, user


def _check_rate_limit(chat_id: int) -> str | None:
    """Check rate limit for heavy commands using Redis TTL keys."""
    try:
        r = redis.from_url(settings.redis_url)
        key = f"telegram:rate:{chat_id}"
        if r.exists(key):
            ttl = r.ttl(key)
            return f"Please wait {ttl}s before running another heavy command."
        r.setex(key, HEAVY_CMD_COOLDOWN, "1")
        return None
    except Exception:
        return None


async def handle_command(session: AsyncSession, chat_id: int, text: str, update: dict) -> None:
    """Dispatch a command to the appropriate handler."""
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower().split("@")[0]  # Strip @botname suffix
    args = parts[1] if len(parts) > 1 else ""

    account, user = await _get_user_for_chat(session, chat_id)
    if not account or not user:
        await send_text(chat_id, "Please link your account first — visit Settings in the web app.")
        return

    await set_tenant_context(session, str(user.tenant_id))

    handlers = {
        "/help": _cmd_help,
        "/jobs": _cmd_jobs,
        "/top": _cmd_top,
        "/job": _cmd_job,
        "/discover": _cmd_discover,
        "/search": _cmd_search,
        "/generate": _cmd_generate,
        "/approve": _cmd_approve,
        "/status": _cmd_status,
        "/unlink": _cmd_unlink,
    }

    handler = handlers.get(cmd)
    if handler:
        await handler(session, chat_id, user, args)
    else:
        await send_text(chat_id, f"Unknown command: {cmd}. Type /help for available commands.")


async def handle_callback(session: AsyncSession, chat_id: int, data: str) -> None:
    """Handle inline keyboard callback queries."""
    account, user = await _get_user_for_chat(session, chat_id)
    if not account or not user:
        return

    await set_tenant_context(session, str(user.tenant_id))

    # Parse callback data: "action:job_id"
    parts = data.split(":")
    if len(parts) < 2:
        return

    action, job_id_str = parts[0], parts[1]
    try:
        job_id = int(job_id_str)
    except ValueError:
        return

    if action == "analyze":
        await _cmd_analyze_job(session, chat_id, user, job_id)
    elif action == "generate":
        await _cmd_generate(session, chat_id, user, str(job_id))
    elif action == "detail":
        await _cmd_job(session, chat_id, user, str(job_id))


async def _cmd_help(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    help_text = (
        "*Available Commands:*\n\n"
        "/jobs — Latest 10 jobs with scores\n"
        "/top — Jobs with fit score >= 70\n"
        "/job <id> — Job details\n"
        "/discover — Run job discovery\n"
        "/search <query> — Search for jobs\n"
        "/generate <id> — Generate resume + cover letter\n"
        "/approve <ids> — Approve jobs for application\n"
        "/status — Application pipeline summary\n"
        "/unlink — Disconnect Telegram\n"
        "/help — Show this message"
    )
    await send_text(chat_id, help_text)


async def _cmd_jobs(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    result = await session.execute(
        select(Job).order_by(Job.scraped_at.desc()).limit(10)
    )
    jobs = result.scalars().all()
    if not jobs:
        await send_text(chat_id, "No jobs found. Try /discover or /search first.")
        return

    lines = ["*Latest Jobs:*\n"]
    for j in jobs:
        # Get fit score if analysis exists
        analysis_result = await session.execute(
            select(Analysis.fit_score).where(Analysis.job_id == j.id).order_by(Analysis.analyzed_at.desc()).limit(1)
        )
        score = analysis_result.scalar_one_or_none()
        score_str = f" ({score}%)" if score else ""
        lines.append(f"#{j.id} {_md_escape(j.title)} @ {_md_escape(j.company)}{score_str}")

    await send_text(chat_id, "\n".join(lines))


async def _cmd_top(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    result = await session.execute(
        select(Job, Analysis.fit_score)
        .join(Analysis, Analysis.job_id == Job.id)
        .where(Analysis.fit_score >= 70)
        .order_by(Analysis.fit_score.desc())
        .limit(10)
    )
    rows = result.all()
    if not rows:
        await send_text(chat_id, "No jobs with fit score >= 70 yet.")
        return

    lines = ["*Top Matches (70%+):*\n"]
    for job, score in rows:
        lines.append(f"#{job.id} {_md_escape(job.title)} @ {_md_escape(job.company)} — *{score}%*")

    await send_text(chat_id, "\n".join(lines))


async def _cmd_job(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    if not args:
        await send_text(chat_id, "Usage: /job <id>")
        return
    try:
        job_id = int(args.strip())
    except ValueError:
        await send_text(chat_id, "Invalid job ID. Usage: /job <id>")
        return

    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        await send_text(chat_id, f"Job #{job_id} not found.")
        return

    analysis_result = await session.execute(
        select(Analysis).where(Analysis.job_id == job_id).order_by(Analysis.analyzed_at.desc()).limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()

    text = f"*{_md_escape(job.title)}*\n{_md_escape(job.company)}"
    if job.location:
        text += f"\n{_md_escape(job.location)}"
    if job.salary_range:
        text += f"\nSalary: {_md_escape(job.salary_range)}"
    if analysis:
        text += f"\n\nFit Score: *{analysis.fit_score}%*"
        if analysis.matching_skills:
            text += f"\nMatching: {', '.join(_md_escape(s) for s in analysis.matching_skills[:5])}"
        if analysis.gaps:
            text += f"\nGaps: {', '.join(_md_escape(g) for g in analysis.gaps[:5])}"

    buttons = [
        [("Analyze", f"analyze:{job_id}"), ("Generate Docs", f"generate:{job_id}")],
    ]
    await send_inline_keyboard(chat_id, text, buttons)


async def _cmd_discover(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    rate_msg = _check_rate_limit(chat_id)
    if rate_msg:
        await send_text(chat_id, rate_msg)
        return

    task = TaskModel(
        tenant_id=user.tenant_id,
        user_id=user.id,
        type="discover",
        status="pending",
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    from src.workers.tasks import run_discovery
    run_discovery.delay(str(task.id), str(user.tenant_id))

    await send_text(chat_id, "Discovery started. I'll notify you when it completes.")


async def _cmd_search(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    if not args:
        await send_text(chat_id, "Usage: /search <query>")
        return

    rate_msg = _check_rate_limit(chat_id)
    if rate_msg:
        await send_text(chat_id, rate_msg)
        return

    await send_text(chat_id, f"Searching for: {_md_escape(args)}...")


async def _cmd_generate(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    if not args:
        await send_text(chat_id, "Usage: /generate <job_id>")
        return
    try:
        job_id = int(args.strip())
    except ValueError:
        await send_text(chat_id, "Invalid job ID.")
        return

    rate_msg = _check_rate_limit(chat_id)
    if rate_msg:
        await send_text(chat_id, rate_msg)
        return

    task = TaskModel(
        tenant_id=user.tenant_id,
        user_id=user.id,
        type="generate",
        status="pending",
        input={"job_id": job_id},
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    from src.workers.tasks import generate_docs
    generate_docs.delay(str(task.id), str(user.tenant_id), job_id)

    await send_text(chat_id, f"Generating docs for job #{job_id}. I'll send them when ready.")


async def _cmd_analyze_job(session: AsyncSession, chat_id: int, user: User, job_id: int) -> None:
    task = TaskModel(
        tenant_id=user.tenant_id,
        user_id=user.id,
        type="analyze",
        status="pending",
        input={"job_id": job_id},
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    from src.workers.tasks import analyze_job
    analyze_job.delay(str(task.id), str(user.tenant_id), job_id)

    await send_text(chat_id, f"Analyzing job #{job_id}...")


async def _cmd_approve(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    if not args:
        await send_text(chat_id, "Usage: /approve <id1> <id2> ...")
        return
    ids = []
    for s in args.split():
        try:
            ids.append(int(s))
        except ValueError:
            pass
    if not ids:
        await send_text(chat_id, "No valid job IDs provided.")
        return

    updated = 0
    for job_id in ids:
        result = await session.execute(
            select(Application).where(Application.job_id == job_id)
        )
        app = result.scalar_one_or_none()
        if app:
            app.status = "approved"
            updated += 1

    await session.commit()
    await send_text(chat_id, f"Approved {updated} job(s).")


async def _cmd_status(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    result = await session.execute(
        select(Application.status, func.count()).group_by(Application.status)
    )
    rows = result.all()
    if not rows:
        await send_text(chat_id, "No applications tracked yet.")
        return

    lines = ["*Application Pipeline:*\n"]
    for status, count in rows:
        lines.append(f"  {status}: {count}")
    await send_text(chat_id, "\n".join(lines))


async def _cmd_unlink(session: AsyncSession, chat_id: int, user: User, args: str) -> None:
    from src.telegram.linking import unlink_telegram
    success = await unlink_telegram(session, str(user.id))
    if success:
        await send_text(chat_id, "Telegram account unlinked. You won't receive notifications here anymore.")
    else:
        await send_text(chat_id, "No linked account found.")
```

- [ ] **Step 2: Write test**

Create `api/tests/test_telegram_handlers.py`:

```python
"""Test Telegram command handler dispatch."""

from src.telegram.handlers import _md_escape


def test_md_escape_special_chars():
    assert _md_escape("hello_world") == "hello\\_world"
    assert _md_escape("*bold*") == "\\*bold\\*"
    assert _md_escape(None) == "N/A"
    assert _md_escape("normal text") == "normal text"
```

- [ ] **Step 3: Run tests**

Run: `cd api && python -m pytest tests/test_telegram_handlers.py -v`
Expected: 1 PASS

- [ ] **Step 4: Commit**

```bash
git add api/src/telegram/handlers.py api/tests/test_telegram_handlers.py
git commit -m "feat: add Telegram command handlers — /jobs, /top, /job, /discover, /generate, /approve, /status"
```

---

### Task 8: Notification Service

**Files:**
- Create: `api/src/notifications/__init__.py`
- Create: `api/src/notifications/dispatcher.py`
- Create: `api/src/notifications/formatters.py`
- Create: `api/src/routes/notifications.py`
- Modify: `api/src/workers/tasks.py`
- Modify: `api/src/app.py`
- Test: `api/tests/test_notifications.py`

- [ ] **Step 1: Create notification package**

Create `api/src/notifications/__init__.py` (empty file).

- [ ] **Step 2: Create formatters.py**

Create `api/src/notifications/formatters.py`:

```python
"""Format task events into human-readable Telegram messages."""


def _md_escape(text) -> str:
    if text is None:
        return "N/A"
    text = str(text)
    for ch in "_*`[":
        text = text.replace(ch, f"\\{ch}")
    return text


def format_task_event(event_type: str, data: dict) -> tuple[str, list[list[tuple[str, str]]]]:
    """Format a task event into (message, inline_buttons).

    Returns:
        (text, buttons) where buttons is a list of rows,
        each row a list of (label, callback_data) tuples.
    """
    task_type = data.get("type", "unknown")
    result = data.get("result", {})
    error = data.get("error", "")

    if event_type == "task:failed":
        return f"Task failed: {error}", []

    if event_type != "task:completed":
        return "", []

    if task_type == "scrape":
        title = _md_escape(result.get("title", "Unknown"))
        company = _md_escape(result.get("company", "Unknown"))
        location = result.get("location", "")
        job_id = result.get("job_id", "")
        text = f"Job scraped: *{title} @ {company}*"
        if location:
            text += f" — {_md_escape(location)}"
        buttons = [[("View Job", f"detail:{job_id}")]] if job_id else []
        return text, buttons

    if task_type == "analyze":
        job_id = result.get("job_id", "")
        score = result.get("fit_score", "?")
        gap_count = result.get("gap_count", 0)
        title = _md_escape(result.get("title", "Job"))
        company = _md_escape(result.get("company", ""))
        text = f"Analysis done: *{title} @ {company}* — Fit: *{score}%* ({gap_count} gaps)"
        buttons = []
        if job_id:
            buttons = [[("View", f"detail:{job_id}"), ("Generate", f"generate:{job_id}")]]
        return text, buttons

    if task_type == "generate":
        job_id = result.get("job_id", "")
        title = _md_escape(result.get("title", "Job"))
        company = _md_escape(result.get("company", ""))
        text = f"Docs ready: *{title} @ {company}*"
        return text, []

    if task_type == "discover":
        count = result.get("count", 0)
        top = result.get("top_match", {})
        text = f"Discovery found *{count} new jobs*."
        if top:
            text += f"\nTop: {_md_escape(top.get('title', ''))} @ {_md_escape(top.get('company', ''))} ({top.get('score', '?')}%)"
        buttons = [[("View Jobs", "detail:0")]] if count > 0 else []
        return text, buttons

    return f"Task completed: {task_type}", []
```

- [ ] **Step 3: Create dispatcher.py**

Create `api/src/notifications/dispatcher.py`:

```python
"""Notification dispatcher — routes task events to Telegram."""

import logging

from sqlalchemy import select

from src.config import settings
from src.db.models import NotificationPreference, TelegramAccount
from src.db.pg import get_session_factory, set_tenant_context
from src.notifications.formatters import format_task_event

logger = logging.getLogger(__name__)


async def notify(tenant_id: str, user_id: str | None, event_type: str, data: dict) -> None:
    """Dispatch a notification to Telegram if the user has it enabled.

    Fire-and-forget: catches all exceptions, logs, never blocks the caller.
    """
    if not settings.telegram_bot_token or not user_id:
        return

    try:
        factory = get_session_factory()
        async with factory() as session:
            await set_tenant_context(session, tenant_id)

            # Check notification preferences
            prefs_result = await session.execute(
                select(NotificationPreference).where(
                    NotificationPreference.user_id == __import__("uuid").UUID(user_id)
                )
            )
            prefs = prefs_result.scalar_one_or_none()

            # Default: telegram_enabled=True if no prefs row
            if prefs and not prefs.telegram_enabled:
                return

            # Get Telegram account
            acct_result = await session.execute(
                select(TelegramAccount).where(
                    TelegramAccount.user_id == __import__("uuid").UUID(user_id),
                    TelegramAccount.is_active == True,  # noqa: E712
                )
            )
            account = acct_result.scalar_one_or_none()
            if not account:
                return

            # Format and send
            text, buttons = format_task_event(event_type, data)
            if not text:
                return

            from src.telegram.sender import send_inline_keyboard, send_text

            if buttons:
                await send_inline_keyboard(account.chat_id, text, buttons)
            else:
                await send_text(account.chat_id, text)

    except Exception:
        logger.exception("Notification dispatch failed for user_id=%s event=%s", user_id, event_type)
```

- [ ] **Step 4: Create notification preferences route**

Create `api/src/routes/notifications.py`:

```python
"""Notification preference endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import current_active_user
from src.db.models import NotificationPreference, User
from src.db.pg import set_tenant_context
from src.deps import get_db_session
from src.schemas import NotificationPreferencesRead, NotificationPreferencesUpdate

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("/preferences", response_model=NotificationPreferencesRead)
async def get_preferences(
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    prefs = result.scalar_one_or_none()
    if prefs:
        return prefs
    return NotificationPreferencesRead()


@router.put("/preferences", response_model=NotificationPreferencesRead)
async def update_preferences(
    data: NotificationPreferencesUpdate,
    session: AsyncSession = Depends(get_db_session),
    user: User = Depends(current_active_user),
):
    await set_tenant_context(session, str(user.tenant_id))
    result = await session.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    prefs = result.scalar_one_or_none()
    if prefs:
        prefs.telegram_enabled = data.telegram_enabled
    else:
        prefs = NotificationPreference(
            tenant_id=user.tenant_id,
            user_id=user.id,
            telegram_enabled=data.telegram_enabled,
        )
        session.add(prefs)
    await session.commit()
    await session.refresh(prefs)
    return prefs
```

- [ ] **Step 5: Wire notify() into Celery workers**

Modify `api/src/workers/tasks.py`. Add `user_id` parameter to all task functions and call `notify()`. 

Update the `scrape_job` function signature to include `user_id`:

```python
@celery_app.task(bind=True, name="scrape_job")
def scrape_job(self, task_id: str, tenant_id: str, url: str, user_id: str | None = None):
```

After each `_publish_event` call, add:

```python
    from src.notifications.dispatcher import notify
    _run_async(notify(tenant_id, user_id, "task:completed", {
        "task_id": task_id, "type": "scrape", "result": {"job_id": job_id},
    }))
```

Do the same for `analyze_job`, `generate_docs`, and `run_discovery` — add `user_id: str | None = None` parameter and `notify()` calls after `_publish_event` for completed and failed events.

For the `_publish_event` + `notify` pattern, add this helper after `_publish_event`:

```python
def _notify_async(tenant_id: str, user_id: str | None, event_type: str, data: dict):
    """Fire-and-forget notification dispatch."""
    if user_id:
        try:
            from src.notifications.dispatcher import notify
            _run_async(notify(tenant_id, user_id, event_type, data))
        except Exception:
            logger.exception("Notification dispatch failed")
```

Then call `_notify_async(tenant_id, user_id, event_type, data)` after each `_publish_event` call.

- [ ] **Step 6: Update route handlers to pass user_id when dispatching tasks**

In `api/src/routes/jobs.py`, when creating tasks and dispatching Celery, pass `user_id=str(user.id)`. For example in the scrape handler, change:

```python
    scrape_job.delay(str(task.id), str(user.tenant_id), data.url)
```
to:
```python
    scrape_job.delay(str(task.id), str(user.tenant_id), data.url, user_id=str(user.id))
```

Do the same for `analyze_job.delay(...)` and `generate_docs.delay(...)` in jobs.py, and `run_discovery.delay(...)` in discovery.py.

- [ ] **Step 7: Register notification routes in app.py**

Add to `api/src/app.py`:

```python
    from src.routes.notifications import router as notifications_router
    app.include_router(notifications_router)
```

- [ ] **Step 8: Write test**

Create `api/tests/test_notifications.py`:

```python
"""Test notification formatters."""

from src.notifications.formatters import format_task_event


def test_format_scrape_completed():
    text, buttons = format_task_event("task:completed", {
        "type": "scrape",
        "result": {"title": "ML Engineer", "company": "Google", "job_id": 42},
    })
    assert "ML Engineer" in text
    assert "Google" in text
    assert len(buttons) == 1


def test_format_analyze_completed():
    text, buttons = format_task_event("task:completed", {
        "type": "analyze",
        "result": {"fit_score": 87, "job_id": 42, "title": "ML", "company": "G"},
    })
    assert "87%" in text


def test_format_task_failed():
    text, buttons = format_task_event("task:failed", {
        "error": "Connection timeout",
    })
    assert "failed" in text.lower()
    assert "timeout" in text.lower()
    assert buttons == []


def test_format_unknown_returns_generic():
    text, buttons = format_task_event("task:completed", {"type": "unknown_type"})
    assert "completed" in text.lower()
```

- [ ] **Step 9: Run tests**

Run: `cd api && python -m pytest tests/test_notifications.py -v`
Expected: 4 PASS

- [ ] **Step 10: Commit**

```bash
git add api/src/notifications/ api/src/routes/notifications.py api/src/workers/tasks.py api/src/routes/jobs.py api/src/routes/discovery.py api/src/app.py api/tests/test_notifications.py
git commit -m "feat: add notification service — dispatcher, formatters, preferences route, worker integration"
```

---

### Task 9: Global Task Panel — Task Store + Badge + Drawer

**Files:**
- Modify: `web/src/stores/task-store.ts`
- Create: `web/src/components/layout/task-badge.tsx`
- Create: `web/src/components/layout/task-drawer.tsx`
- Modify: `web/src/hooks/use-task-stream.ts`
- Modify: `web/src/components/layout/icon-rail.tsx`

- [ ] **Step 1: Update task store**

Replace `web/src/stores/task-store.ts`:

```typescript
import { create } from "zustand";

export interface RunningTask {
  id: string;
  type: string;
  progress: number;
  message?: string;
  startedAt?: number;
}

export interface CompletedTask {
  id: string;
  type: string;
  status: "completed" | "failed";
  result?: Record<string, unknown>;
  error?: string;
  completedAt: number;
}

interface TaskState {
  tasks: RunningTask[];
  recentTasks: CompletedTask[];
  drawerOpen: boolean;
  addTask: (task: RunningTask) => void;
  updateTask: (id: string, updates: Partial<RunningTask>) => void;
  completeTask: (id: string, result?: Record<string, unknown>) => void;
  failTask: (id: string, error?: string) => void;
  removeTask: (id: string) => void;
  toggleDrawer: () => void;
  clear: () => void;
}

const MAX_RECENT = 10;
const RECENT_TTL_MS = 60 * 60 * 1000; // 1 hour

function pruneRecent(tasks: CompletedTask[]): CompletedTask[] {
  const cutoff = Date.now() - RECENT_TTL_MS;
  return tasks.filter((t) => t.completedAt > cutoff).slice(0, MAX_RECENT);
}

export const useTaskStore = create<TaskState>((set) => ({
  tasks: [],
  recentTasks: [],
  drawerOpen: false,
  addTask: (task) =>
    set((s) => ({
      tasks: s.tasks.some((t) => t.id === task.id)
        ? s.tasks
        : [...s.tasks, { ...task, startedAt: task.startedAt ?? Date.now() }],
    })),
  updateTask: (id, updates) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, ...updates } : t)),
    })),
  completeTask: (id, result) =>
    set((s) => {
      const task = s.tasks.find((t) => t.id === id);
      return {
        tasks: s.tasks.filter((t) => t.id !== id),
        recentTasks: pruneRecent([
          { id, type: task?.type ?? "unknown", status: "completed", result, completedAt: Date.now() },
          ...s.recentTasks,
        ]),
      };
    }),
  failTask: (id, error) =>
    set((s) => {
      const task = s.tasks.find((t) => t.id === id);
      return {
        tasks: s.tasks.filter((t) => t.id !== id),
        recentTasks: pruneRecent([
          { id, type: task?.type ?? "unknown", status: "failed", error, completedAt: Date.now() },
          ...s.recentTasks,
        ]),
      };
    }),
  removeTask: (id) => set((s) => ({ tasks: s.tasks.filter((t) => t.id !== id) })),
  toggleDrawer: () => set((s) => ({ drawerOpen: !s.drawerOpen })),
  clear: () => set({ tasks: [], recentTasks: [] }),
}));
```

- [ ] **Step 2: Update use-task-stream.ts to use completeTask/failTask**

In `web/src/hooks/use-task-stream.ts`, update the imports and event handlers:

Replace the `removeTask` destructure with `completeTask` and `failTask`:

```typescript
  const { addTask, updateTask, completeTask, failTask } = useTaskStore();
```

Replace the `task:completed` handler:

```typescript
      es.addEventListener("task:completed", (e) => {
        const data = JSON.parse(e.data);
        completeTask(data.task_id, data.result);
        toast.success(`${data.type} completed`);
        if (data.type === "scrape" || data.type === "discover") {
          queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
        }
        if (data.type === "analyze") {
          queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
          if (data.result?.job_id) {
            queryClient.invalidateQueries({ queryKey: queryKeys.analysis.byJob(data.result.job_id) });
          }
        }
        if (data.type === "generate") {
          if (data.result?.job_id) {
            queryClient.invalidateQueries({ queryKey: queryKeys.documents.byJob(data.result.job_id) });
          }
        }
      });
```

Replace the `task:failed` handler:

```typescript
      es.addEventListener("task:failed", (e) => {
        const data = JSON.parse(e.data);
        failTask(data.task_id, data.error);
        toast.error(`${data.type} failed: ${data.error || "Unknown error"}`);
      });
```

Update the dependency array to include `completeTask` and `failTask` instead of `removeTask`:

```typescript
  }, [isAuthenticated, token, addTask, updateTask, completeTask, failTask, queryClient]);
```

- [ ] **Step 3: Create task-badge.tsx**

Create `web/src/components/layout/task-badge.tsx`:

```typescript
import { Activity } from "lucide-react";
import { useTaskStore } from "@/stores/task-store";
import { cn } from "@/lib/utils";

export function TaskBadge() {
  const taskCount = useTaskStore((s) => s.tasks.length);
  const toggleDrawer = useTaskStore((s) => s.toggleDrawer);

  return (
    <button
      onClick={toggleDrawer}
      className="relative flex h-9 w-full items-center gap-3 rounded-md px-2 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
      aria-label={`${taskCount} active tasks`}
    >
      <Activity className="h-5 w-5 shrink-0" />
      <span className="truncate text-sm opacity-0 transition-opacity duration-200 group-hover/rail:opacity-100">
        Tasks
      </span>
      {taskCount > 0 && (
        <span
          className={cn(
            "absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-blue-600 px-1 text-[10px] font-medium text-white",
            "animate-pulse",
          )}
        >
          {taskCount}
        </span>
      )}
    </button>
  );
}
```

- [ ] **Step 4: Create task-drawer.tsx**

Create `web/src/components/layout/task-drawer.tsx`:

```typescript
import { BarChart3, Briefcase, CheckCircle2, Compass, FileText, XCircle } from "lucide-react";
import { useNavigate } from "react-router";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Progress } from "@/components/ui/progress";
import { useTaskStore, type CompletedTask, type RunningTask } from "@/stores/task-store";
import { cn } from "@/lib/utils";

const typeIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  scrape: Briefcase,
  analyze: BarChart3,
  generate: FileText,
  discover: Compass,
};

const typeLabels: Record<string, string> = {
  scrape: "Scraping job",
  analyze: "Analyzing job",
  generate: "Generating docs",
  discover: "Running discovery",
};

function elapsed(startedAt?: number): string {
  if (!startedAt) return "";
  const sec = Math.floor((Date.now() - startedAt) / 1000);
  if (sec < 60) return `${sec}s`;
  return `${Math.floor(sec / 60)}m ${sec % 60}s`;
}

function timeAgo(ts: number): string {
  const sec = Math.floor((Date.now() - ts) / 1000);
  if (sec < 60) return "just now";
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  return `${Math.floor(sec / 3600)}h ago`;
}

function RunningTaskRow({ task }: { task: RunningTask }) {
  const Icon = typeIcons[task.type] || Briefcase;
  return (
    <div className="flex items-center gap-3 rounded-md border p-3">
      <Icon className="h-5 w-5 shrink-0 text-blue-500" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">{typeLabels[task.type] || task.type}</span>
          <span className="text-xs text-muted-foreground">{elapsed(task.startedAt)}</span>
        </div>
        {task.message && <p className="truncate text-xs text-muted-foreground">{task.message}</p>}
        <Progress value={task.progress} className="mt-1.5 h-1.5" />
      </div>
    </div>
  );
}

function CompletedTaskRow({ task }: { task: CompletedTask }) {
  const navigate = useNavigate();
  const Icon = task.status === "completed" ? CheckCircle2 : XCircle;
  const iconColor = task.status === "completed" ? "text-green-500" : "text-red-500";

  function handleClick() {
    if (task.status === "completed" && task.result?.job_id) {
      navigate(`/jobs/${task.result.job_id}`);
    }
  }

  return (
    <button
      onClick={handleClick}
      className={cn(
        "flex w-full items-center gap-3 rounded-md border p-3 text-left transition-colors",
        task.result?.job_id && "cursor-pointer hover:bg-accent",
      )}
    >
      <Icon className={cn("h-5 w-5 shrink-0", iconColor)} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between text-sm">
          <span>{typeLabels[task.type] || task.type}</span>
          <span className="text-xs text-muted-foreground">{timeAgo(task.completedAt)}</span>
        </div>
        {task.error && <p className="truncate text-xs text-red-500">{task.error}</p>}
      </div>
    </button>
  );
}

export function TaskDrawer() {
  const drawerOpen = useTaskStore((s) => s.drawerOpen);
  const toggleDrawer = useTaskStore((s) => s.toggleDrawer);
  const tasks = useTaskStore((s) => s.tasks);
  const recentTasks = useTaskStore((s) => s.recentTasks);

  return (
    <Sheet open={drawerOpen} onOpenChange={toggleDrawer}>
      <SheetContent side="right" className="w-[380px] sm:w-[420px]">
        <SheetHeader>
          <SheetTitle>Tasks</SheetTitle>
        </SheetHeader>
        <div className="mt-4 space-y-4 overflow-auto">
          {tasks.length > 0 && (
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Running</h3>
              <div className="space-y-2">
                {tasks.map((t) => <RunningTaskRow key={t.id} task={t} />)}
              </div>
            </div>
          )}
          {recentTasks.length > 0 && (
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Recent</h3>
              <div className="space-y-2">
                {recentTasks.map((t) => <CompletedTaskRow key={t.id} task={t} />)}
              </div>
            </div>
          )}
          {tasks.length === 0 && recentTasks.length === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">No tasks yet</p>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
```

- [ ] **Step 5: Add TaskBadge to icon rail**

In `web/src/components/layout/icon-rail.tsx`, add the import and component:

Add import at top:
```typescript
import { TaskBadge } from "./task-badge";
```

Add `<TaskBadge />` between `<div className="mt-auto" />` and the bottomItems map:

```typescript
        <div className="mt-auto" />
        <TaskBadge />
        {bottomItems.map((item) => (
```

- [ ] **Step 6: Add TaskDrawer to app-shell**

In `web/src/components/layout/app-shell.tsx`, add import and render:

Add import:
```typescript
import { TaskDrawer } from "./task-drawer";
```

Add `<TaskDrawer />` inside the outer div, after the main content div:

```typescript
    <div className="flex h-screen overflow-hidden">
      <IconRail />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar title={title} />
        <main className="flex-1 overflow-auto p-5">
          <Outlet />
        </main>
      </div>
      <TaskDrawer />
    </div>
```

- [ ] **Step 7: Build to verify TypeScript**

Run: `cd web && npx tsc --noEmit`
Expected: 0 errors

- [ ] **Step 8: Commit**

```bash
git add web/src/stores/task-store.ts web/src/hooks/use-task-stream.ts web/src/components/layout/task-badge.tsx web/src/components/layout/task-drawer.tsx web/src/components/layout/icon-rail.tsx web/src/components/layout/app-shell.tsx
git commit -m "feat: add global task panel — badge on icon rail, slide-out drawer with running/recent tasks"
```

---

### Task 10: Telegram Section in Settings Page

**Files:**
- Modify: `web/src/pages/settings.tsx`

- [ ] **Step 1: Add TelegramSection and NotificationSection to settings page**

Add these sections to `web/src/pages/settings.tsx`. After the Appearance card and before `{isAdmin && <TeamSection />}`:

```typescript
      <TelegramSection />
      <NotificationSection />
```

Add the two new components inside the same file, before `function TeamSection()`:

```typescript
function TelegramSection() {
  const queryClient = useQueryClient();

  const statusQuery = useQuery({
    queryKey: queryKeys.telegram.status,
    queryFn: () => apiClient.get("/api/telegram/status").then((r) => r.data),
  });

  const linkMutation = useMutation({
    mutationFn: () => apiClient.post("/api/telegram/link-code").then((r) => r.data),
    onError: (err: any) => toast.error(err.response?.data?.detail || "Failed to generate link"),
  });

  const unlinkMutation = useMutation({
    mutationFn: () => apiClient.delete("/api/telegram/unlink"),
    onSuccess: () => {
      toast.success("Telegram unlinked");
      queryClient.invalidateQueries({ queryKey: queryKeys.telegram.status });
    },
    onError: () => toast.error("Failed to unlink"),
  });

  const status = statusQuery.data;

  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Telegram</CardTitle></CardHeader>
      <CardContent className="space-y-3 text-sm">
        {status?.linked ? (
          <>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Connected as</span>
              <span>@{status.username || "unknown"}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => unlinkMutation.mutate()}
              disabled={unlinkMutation.isPending}
            >
              Disconnect
            </Button>
          </>
        ) : (
          <>
            <p className="text-muted-foreground">Connect your Telegram account to receive notifications and run commands from the bot.</p>
            {linkMutation.data?.deep_link ? (
              <div className="space-y-2">
                <a
                  href={linkMutation.data.deep_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
                >
                  Open in Telegram
                </a>
                <p className="text-xs text-muted-foreground">Code: {linkMutation.data.code} (expires in 10 min)</p>
              </div>
            ) : (
              <Button size="sm" onClick={() => linkMutation.mutate()} disabled={linkMutation.isPending}>
                Connect Telegram
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function NotificationSection() {
  const queryClient = useQueryClient();

  const prefsQuery = useQuery({
    queryKey: queryKeys.notifications.preferences,
    queryFn: () => apiClient.get("/api/notifications/preferences").then((r) => r.data),
  });

  const updateMutation = useMutation({
    mutationFn: (telegram_enabled: boolean) =>
      apiClient.put("/api/notifications/preferences", { telegram_enabled }).then((r) => r.data),
    onSuccess: () => {
      toast.success("Preferences saved");
      queryClient.invalidateQueries({ queryKey: queryKeys.notifications.preferences });
    },
  });

  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Notifications</CardTitle></CardHeader>
      <CardContent>
        <div className="flex items-center justify-between text-sm">
          <span>Telegram notifications</span>
          <input
            type="checkbox"
            className="h-4 w-4"
            checked={prefsQuery.data?.telegram_enabled ?? true}
            onChange={(e) => updateMutation.mutate(e.target.checked)}
          />
        </div>
      </CardContent>
    </Card>
  );
}
```

Also add `queryKeys` to the imports if not already imported (it already is).

- [ ] **Step 2: Build to verify TypeScript**

Run: `cd web && npx tsc --noEmit`
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/settings.tsx
git commit -m "feat: add Telegram linking and notification preferences to Settings page"
```

---

### Task 11: Mobile Responsive — Bottom Nav + Layout Adjustments

**Files:**
- Create: `web/src/components/layout/mobile-nav.tsx`
- Modify: `web/src/components/layout/icon-rail.tsx`
- Modify: `web/src/components/layout/app-shell.tsx`
- Modify: `web/src/components/layout/top-bar.tsx`
- Modify: `web/src/pages/dashboard.tsx`
- Modify: `web/src/pages/jobs/detail.tsx`
- Modify: `web/src/pages/discover.tsx`
- Modify: `web/src/pages/billing/plans.tsx`

- [ ] **Step 1: Create mobile-nav.tsx**

Create `web/src/components/layout/mobile-nav.tsx`:

```typescript
import { Briefcase, Compass, Globe, LayoutDashboard, Menu } from "lucide-react";
import { NavLink } from "react-router";
import { useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { MessageSquare, Settings, TrendingUp, User, CreditCard } from "lucide-react";

const tabs = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Home" },
  { to: "/jobs", icon: Briefcase, label: "Jobs" },
  { to: "/discover", icon: Compass, label: "Discover" },
  { to: "/search", icon: Globe, label: "Search" },
];

const moreItems = [
  { to: "/skills", icon: TrendingUp, label: "Skills" },
  { to: "/profile", icon: User, label: "Profile" },
  { to: "/answers", icon: MessageSquare, label: "Answers" },
  { to: "/settings", icon: Settings, label: "Settings" },
  { to: "/billing", icon: CreditCard, label: "Billing" },
];

export function MobileNav() {
  const [moreOpen, setMoreOpen] = useState(false);

  return (
    <>
      <nav className="fixed inset-x-0 bottom-0 z-50 flex h-14 items-center justify-around border-t bg-background md:hidden">
        {tabs.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center gap-0.5 px-3 py-1 text-muted-foreground",
                isActive && "text-blue-600 dark:text-blue-400",
              )
            }
          >
            <item.icon className="h-5 w-5" />
            <span className="text-[10px]">{item.label}</span>
          </NavLink>
        ))}
        <button
          onClick={() => setMoreOpen(true)}
          className="flex flex-col items-center gap-0.5 px-3 py-1 text-muted-foreground"
        >
          <Menu className="h-5 w-5" />
          <span className="text-[10px]">More</span>
        </button>
      </nav>
      <Sheet open={moreOpen} onOpenChange={setMoreOpen}>
        <SheetContent side="bottom" className="rounded-t-xl">
          <SheetHeader>
            <SheetTitle>More</SheetTitle>
          </SheetHeader>
          <div className="grid grid-cols-3 gap-4 py-4">
            {moreItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMoreOpen(false)}
                className="flex flex-col items-center gap-1.5 rounded-lg p-3 text-muted-foreground hover:bg-accent"
              >
                <item.icon className="h-6 w-6" />
                <span className="text-xs">{item.label}</span>
              </NavLink>
            ))}
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
```

- [ ] **Step 2: Hide icon rail on mobile**

In `web/src/components/layout/icon-rail.tsx`, change the nav className:

Replace:
```typescript
      <nav className="group/rail flex w-[52px] flex-col items-center gap-1 border-r bg-muted/40 px-2 py-3 transition-all duration-200 hover:w-[200px]">
```
With:
```typescript
      <nav className="group/rail hidden md:flex w-[52px] flex-col items-center gap-1 border-r bg-muted/40 px-2 py-3 transition-all duration-200 hover:w-[200px]">
```

- [ ] **Step 3: Update app-shell.tsx for mobile**

Replace `web/src/components/layout/app-shell.tsx`:

```typescript
import { Outlet, useLocation } from "react-router";
import { useTaskStream } from "@/hooks/use-task-stream";
import { IconRail } from "./icon-rail";
import { TopBar } from "./top-bar";
import { TaskDrawer } from "./task-drawer";
import { MobileNav } from "./mobile-nav";

const pageTitles: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/jobs": "Jobs",
  "/discover": "Discover",
  "/search": "Search",
  "/skills": "Skills",
  "/profile": "Profile",
  "/answers": "Answers",
  "/settings": "Settings",
  "/billing": "Billing",
  "/billing/plans": "Plans",
  "/billing/usage": "Usage",
  "/billing/history": "History",
};

export function AppShell() {
  const location = useLocation();
  useTaskStream();
  const title =
    pageTitles[location.pathname] ??
    Object.entries(pageTitles).find(([prefix]) => location.pathname.startsWith(prefix))?.[1] ??
    "JobAssist";
  return (
    <div className="flex h-screen overflow-hidden">
      <IconRail />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar title={title} />
        <main className="flex-1 overflow-auto p-4 pb-20 md:p-5 md:pb-5">
          <Outlet />
        </main>
      </div>
      <TaskDrawer />
      <MobileNav />
    </div>
  );
}
```

- [ ] **Step 4: Add TaskBadge to top-bar for mobile**

In `web/src/components/layout/top-bar.tsx`, add the TaskBadge import and render it for mobile:

Add import:
```typescript
import { TaskBadge } from "./task-badge";
```

In the right side div (before the plan badge), add a mobile-only task badge:

```typescript
        <div className="flex md:hidden">
          <TaskBadge />
        </div>
```

- [ ] **Step 5: Make dashboard responsive**

In `web/src/pages/dashboard.tsx`, find the stats cards grid and update to 2x2 on mobile. Change:

```
grid-cols-4
```
to:
```
grid-cols-2 md:grid-cols-4
```

- [ ] **Step 6: Make job detail responsive**

In `web/src/pages/jobs/detail.tsx`, find the two-column layout container. Change from `flex` row to stack on mobile:

Change the two-column container from:
```
className="flex gap-6"
```
to:
```
className="flex flex-col gap-6 md:flex-row"
```

And the action panel from a fixed width to full width on mobile:
```
className="w-full md:w-72 shrink-0"
```

- [ ] **Step 7: Make discover responsive**

In `web/src/pages/discover.tsx`, change the config grid from `grid-cols-2` to `grid-cols-1 md:grid-cols-2`.

- [ ] **Step 8: Make billing plans responsive**

In `web/src/pages/billing/plans.tsx`, change from `grid-cols-3` to `grid-cols-1 md:grid-cols-3`.

- [ ] **Step 9: Build to verify TypeScript**

Run: `cd web && npx tsc --noEmit`
Expected: 0 errors

- [ ] **Step 10: Commit**

```bash
git add web/src/components/layout/ web/src/pages/dashboard.tsx web/src/pages/jobs/detail.tsx web/src/pages/discover.tsx web/src/pages/billing/plans.tsx
git commit -m "feat: add mobile responsive layout — bottom nav, responsive grids, task badge in top bar"
```

---

### Task 12: Docker + Dependency Updates

**Files:**
- Modify: `docker-compose.yml`
- Modify: `api/pyproject.toml`

- [ ] **Step 1: Update docker-compose.yml**

Add Telegram env vars to the `api` service environment:

```yaml
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}
      - TELEGRAM_WEBHOOK_BASE_URL=${TELEGRAM_WEBHOOK_BASE_URL:-}
```

Add `TELEGRAM_BOT_TOKEN` to the `worker` service environment:

```yaml
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN:-}
```

- [ ] **Step 2: Verify pyproject.toml has python-telegram-bot**

Confirm `api/pyproject.toml` dependencies include:

```
    "python-telegram-bot>=21.0",
```

(This was added in Task 5.)

- [ ] **Step 3: Rebuild Docker**

```bash
docker compose build api --no-cache
docker compose up -d api worker
```

- [ ] **Step 4: Run migration**

```bash
DATABASE_URL=postgresql://jobapp:jobapp_dev@localhost:5432/jobapp alembic upgrade head
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add Telegram env vars to Docker Compose"
```

---

### Task 13: E2E Test Setup + Auth Tests

**Files:**
- Create: `e2e/package.json`
- Create: `e2e/playwright.config.ts`
- Create: `e2e/tsconfig.json`
- Create: `e2e/fixtures/auth.ts`
- Create: `e2e/fixtures/seed.ts`
- Create: `e2e/tests/auth.spec.ts`

- [ ] **Step 1: Create e2e package.json**

Create `e2e/package.json`:

```json
{
  "name": "e2e-tests",
  "private": true,
  "scripts": {
    "test": "playwright test",
    "test:ui": "playwright test --ui",
    "test:headed": "playwright test --headed"
  },
  "devDependencies": {
    "@playwright/test": "^1.52.0",
    "axios": "^1.14.0"
  }
}
```

- [ ] **Step 2: Create playwright config**

Create `e2e/playwright.config.ts`:

```typescript
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  retries: 1,
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "mobile-safari", use: { ...devices["iPhone 13"] } },
  ],
});
```

- [ ] **Step 3: Create tsconfig.json**

Create `e2e/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["**/*.ts"]
}
```

- [ ] **Step 4: Create auth fixture**

Create `e2e/fixtures/auth.ts`:

```typescript
import { type Page } from "@playwright/test";
import axios from "axios";

const API_URL = "http://localhost:8000";

export interface TestUser {
  email: string;
  password: string;
  accessToken: string;
}

let userCounter = 0;

export async function createTestUser(): Promise<TestUser> {
  const email = `e2e-${Date.now()}-${userCounter++}@test.com`;
  const password = "testpass123";

  await axios.post(`${API_URL}/api/auth/register`, { email, password });

  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);
  const loginResp = await axios.post(`${API_URL}/api/auth/login`, form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });

  return { email, password, accessToken: loginResp.data.access_token };
}

export async function loginViaUI(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /sign in|log in/i }).click();
  await page.waitForURL("**/dashboard");
}

export async function registerViaUI(page: Page, email: string, password: string) {
  await page.goto("/register");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: /sign up|register|create/i }).click();
}
```

- [ ] **Step 5: Create seed fixture**

Create `e2e/fixtures/seed.ts`:

```typescript
import axios from "axios";

const API_URL = "http://localhost:8000";

export async function seedJobs(accessToken: string, count: number = 3) {
  const headers = { Authorization: `Bearer ${accessToken}` };

  // Seed jobs by calling scrape (or direct DB insert if scrape requires external API)
  // For E2E, we POST to the scrape endpoint with test URLs
  // Since scraping requires Firecrawl, we'll check if jobs exist first
  const resp = await axios.get(`${API_URL}/api/jobs?limit=1`, { headers });
  if (resp.data.length > 0) return; // Already seeded

  // If no jobs exist, the tests that need them will handle the empty state
}

export async function seedSearchConfig(accessToken: string) {
  const headers = { Authorization: `Bearer ${accessToken}` };
  await axios.post(
    `${API_URL}/api/discovery/configs`,
    { name: "Test Config", config_type: "search_query", config: { query: "test", location: "Remote" } },
    { headers },
  );
}
```

- [ ] **Step 6: Create auth tests**

Create `e2e/tests/auth.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";

const email = `auth-${Date.now()}@test.com`;
const password = "testpass123";

test.describe("Auth", () => {
  test("register new account", async ({ page }) => {
    await page.goto("/register");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /sign up|register|create/i }).click();
    // After registration, user should be redirected to login or auto-logged in
    await expect(page).toHaveURL(/\/(login|dashboard)/);
  });

  test("login with valid credentials", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    await expect(page).toHaveURL("**/dashboard");
  });

  test("login with invalid credentials shows error", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("wrong@test.com");
    await page.getByLabel("Password").fill("wrongpass");
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    await expect(page.getByText(/invalid|failed|error/i)).toBeVisible({ timeout: 5000 });
  });

  test("logout redirects to login", async ({ page }) => {
    // Login first
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    await expect(page).toHaveURL("**/dashboard");

    // Logout via user menu
    await page.getByRole("button", { name: /avatar|user/i }).first().click();
    await page.getByText("Sign out").click();
    await expect(page).toHaveURL("**/login");
  });

  test("refresh token preserves session across reload", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /sign in|log in/i }).click();
    await expect(page).toHaveURL("**/dashboard");

    // Reload — should stay on dashboard (refresh cookie restores session)
    await page.reload();
    await expect(page).toHaveURL("**/dashboard", { timeout: 5000 });
  });
});
```

- [ ] **Step 7: Install and run**

```bash
cd e2e && npm install && npx playwright install chromium
npx playwright test tests/auth.spec.ts --project=chromium
```

Expected: 5 tests, majority PASS (some may need adjustment based on exact UI text)

- [ ] **Step 8: Commit**

```bash
git add e2e/
git commit -m "feat: add E2E test setup with Playwright — auth test suite (5 tests)"
```

---

### Task 14: E2E Tests — All Remaining Suites

**Files:**
- Create: `e2e/tests/dashboard.spec.ts`
- Create: `e2e/tests/jobs.spec.ts`
- Create: `e2e/tests/discovery.spec.ts`
- Create: `e2e/tests/search.spec.ts`
- Create: `e2e/tests/profile.spec.ts`
- Create: `e2e/tests/answers.spec.ts`
- Create: `e2e/tests/skills.spec.ts`
- Create: `e2e/tests/settings.spec.ts`
- Create: `e2e/tests/billing.spec.ts`
- Create: `e2e/tests/task-panel.spec.ts`
- Create: `e2e/tests/telegram.spec.ts`
- Create: `e2e/tests/mobile.spec.ts`
- Create: `e2e/fixtures/telegram-mock.ts`

- [ ] **Step 1: Create telegram-mock fixture**

Create `e2e/fixtures/telegram-mock.ts`:

```typescript
import axios from "axios";

const API_URL = "http://localhost:8000";

/**
 * Simulate a Telegram /start command via the webhook endpoint.
 */
export async function simulateStartCommand(botToken: string, chatId: number, code: string, username: string = "testuser") {
  const update = {
    update_id: Date.now(),
    message: {
      message_id: Date.now(),
      from: { id: chatId, is_bot: false, first_name: "Test", username },
      chat: { id: chatId, type: "private" },
      text: `/start ${code}`,
    },
  };
  return axios.post(`${API_URL}/api/telegram/webhook/${botToken}`, update);
}

/**
 * Simulate a Telegram command via the webhook endpoint.
 */
export async function simulateCommand(botToken: string, chatId: number, command: string) {
  const update = {
    update_id: Date.now(),
    message: {
      message_id: Date.now(),
      from: { id: chatId, is_bot: false, first_name: "Test" },
      chat: { id: chatId, type: "private" },
      text: command,
    },
  };
  return axios.post(`${API_URL}/api/telegram/webhook/${botToken}`, update);
}
```

- [ ] **Step 2: Create all remaining test suites**

Create `e2e/tests/dashboard.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Dashboard", () => {
  test.beforeEach(async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
  });

  test("stats cards render", async ({ page }) => {
    await expect(page.getByText(/total jobs/i)).toBeVisible();
    await expect(page.getByText(/avg fit/i)).toBeVisible();
  });

  test("quick scrape bar is visible", async ({ page }) => {
    await expect(page.getByPlaceholder(/paste.*url/i)).toBeVisible();
  });
});
```

Create `e2e/tests/jobs.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Jobs", () => {
  test.beforeEach(async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/jobs");
  });

  test("job list page loads", async ({ page }) => {
    await expect(page.getByText(/jobs/i)).toBeVisible();
  });

  test("search input exists", async ({ page }) => {
    await expect(page.getByPlaceholder(/search/i)).toBeVisible();
  });

  test("sort select exists", async ({ page }) => {
    await expect(page.getByText(/scraped_at|sort/i)).toBeVisible();
  });
});
```

Create `e2e/tests/discovery.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Discovery", () => {
  test.beforeEach(async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/discover");
  });

  test("discover page loads", async ({ page }) => {
    await expect(page.getByText(/discover/i)).toBeVisible();
  });

  test("add config button exists", async ({ page }) => {
    await expect(page.getByRole("button", { name: /add|new|config/i })).toBeVisible();
  });
});
```

Create `e2e/tests/search.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Search", () => {
  test("search page loads", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/search");
    await expect(page.getByPlaceholder(/search|query/i)).toBeVisible();
  });
});
```

Create `e2e/tests/profile.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Profile", () => {
  test.beforeEach(async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/profile");
  });

  test("profile page loads with name field", async ({ page }) => {
    await expect(page.getByLabel(/full name|name/i)).toBeVisible();
  });

  test("import button exists", async ({ page }) => {
    await expect(page.getByRole("button", { name: /import/i })).toBeVisible();
  });
});
```

Create `e2e/tests/answers.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Answers", () => {
  test.beforeEach(async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/answers");
  });

  test("answers page loads", async ({ page }) => {
    await expect(page.getByText(/answers/i)).toBeVisible();
  });

  test("add answer button exists", async ({ page }) => {
    await expect(page.getByRole("button", { name: /add/i })).toBeVisible();
  });
});
```

Create `e2e/tests/skills.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Skills", () => {
  test("skills page loads", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/skills");
    await expect(page.getByText(/skills/i)).toBeVisible();
  });
});
```

Create `e2e/tests/settings.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Settings", () => {
  test.beforeEach(async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/settings");
  });

  test("account info displays email", async ({ page }) => {
    await expect(page.getByText(/email/i)).toBeVisible();
  });

  test("theme toggle exists", async ({ page }) => {
    await expect(page.getByText(/theme/i)).toBeVisible();
  });

  test("telegram section shows connect button", async ({ page }) => {
    await expect(page.getByText(/telegram/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /connect/i })).toBeVisible();
  });
});
```

Create `e2e/tests/billing.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Billing", () => {
  test("plans page loads", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/billing/plans");
    await expect(page.getByText(/free|pro|enterprise/i)).toBeVisible();
  });

  test("usage page loads", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/billing/usage");
    await expect(page.getByText(/usage/i)).toBeVisible();
  });
});
```

Create `e2e/tests/task-panel.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.describe("Task Panel", () => {
  test("task badge is visible in nav", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    // TaskBadge renders an Activity icon
    await expect(page.locator("[aria-label*='tasks']").first()).toBeVisible();
  });

  test("clicking badge opens drawer", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.locator("[aria-label*='tasks']").first().click();
    await expect(page.getByText(/no tasks yet|running|recent/i)).toBeVisible();
  });
});
```

Create `e2e/tests/telegram.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";
import axios from "axios";

const API_URL = "http://localhost:8000";

test.describe("Telegram Integration", () => {
  test("generate link code via API", async () => {
    const user = await createTestUser();
    const resp = await axios.post(`${API_URL}/api/telegram/link-code`, null, {
      headers: { Authorization: `Bearer ${user.accessToken}` },
    });
    expect(resp.status).toBe(200);
    expect(resp.data.code).toBeTruthy();
  });

  test("telegram status shows unlinked", async () => {
    const user = await createTestUser();
    const resp = await axios.get(`${API_URL}/api/telegram/status`, {
      headers: { Authorization: `Bearer ${user.accessToken}` },
    });
    expect(resp.data.linked).toBe(false);
  });

  test("connect telegram button shown in settings", async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
    await page.goto("/settings");
    await expect(page.getByRole("button", { name: /connect.*telegram/i })).toBeVisible();
  });
});
```

Create `e2e/tests/mobile.spec.ts`:

```typescript
import { test, expect, devices } from "@playwright/test";
import { loginViaUI, createTestUser } from "../fixtures/auth";

test.use(devices["iPhone 13"]);

test.describe("Mobile Layout", () => {
  test.beforeEach(async ({ page }) => {
    const user = await createTestUser();
    await loginViaUI(page, user.email, user.password);
  });

  test("bottom nav renders", async ({ page }) => {
    // Bottom nav should have Home, Jobs, Discover, Search, More
    await expect(page.getByText("Home")).toBeVisible();
    await expect(page.getByText("Jobs")).toBeVisible();
    await expect(page.getByText("More")).toBeVisible();
  });

  test("more menu opens remaining items", async ({ page }) => {
    await page.getByText("More").click();
    await expect(page.getByText("Skills")).toBeVisible();
    await expect(page.getByText("Settings")).toBeVisible();
  });

  test("icon rail is hidden", async ({ page }) => {
    // Icon rail has hidden md:flex, should not be visible on mobile
    const rail = page.locator("nav.group\\/rail");
    await expect(rail).toBeHidden();
  });
});
```

- [ ] **Step 3: Run all E2E tests**

```bash
cd e2e && npx playwright test --project=chromium
```

Expected: Most tests PASS. Fix any that fail due to exact text mismatches.

- [ ] **Step 4: Commit**

```bash
git add e2e/
git commit -m "feat: add full E2E test coverage — 13 suites covering auth, pages, task panel, telegram, mobile"
```

---

### Task 15: Run Full Test Suite + Lint

**Files:** None (verification only)

- [ ] **Step 1: Run backend tests**

```bash
cd api && python -m pytest tests/ -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 2: Run frontend TypeScript check**

```bash
cd web && npx tsc --noEmit
```

Expected: 0 errors

- [ ] **Step 3: Run frontend build**

```bash
cd web && npm run build
```

Expected: Build succeeds

- [ ] **Step 4: Run backend lint**

```bash
cd api && python -m ruff check src/ tests/
```

Expected: No errors (or only pre-existing ones)

- [ ] **Step 5: Run E2E tests (if Docker stack is running)**

```bash
cd e2e && npx playwright test --project=chromium
```

- [ ] **Step 6: Final commit with any fixes**

```bash
git add -A && git commit -m "chore: fix lint and type errors from Phase 4 implementation"
```
