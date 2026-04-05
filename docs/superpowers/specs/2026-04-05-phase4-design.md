# Phase 4: Telegram Bot, Task Panel, Refresh Tokens, Mobile, E2E Tests

## Overview

Phase 4 adds real-time task visibility across the web app, a full bidirectional Telegram bot for notifications and actions, proper refresh token authentication, mobile responsive layout, and comprehensive E2E test coverage.

**Prerequisites:** Phase 2 (FastAPI backend) and Phase 3 (React frontend) complete. Docker stack running with PostgreSQL, Redis, MinIO, Celery, FastAPI, and React/nginx.

---

## 1. Database Schema Changes

### New Tables

#### `telegram_accounts`

Stores linked Telegram accounts for SaaS users.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, default `gen_random_uuid()` |
| `tenant_id` | UUID | NOT NULL, RLS-protected |
| `user_id` | UUID | FK → users, NOT NULL |
| `chat_id` | BIGINT | UNIQUE, NOT NULL |
| `username` | TEXT | nullable — Telegram @username for display |
| `is_active` | BOOLEAN | default true — toggle notifications without unlinking |
| `linked_at` | TIMESTAMPTZ | default `now()` |

RLS policy: `tenant_id = current_setting('app.current_tenant')::uuid`

#### `telegram_link_codes`

Short-lived verification codes for the deep link account linking flow.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, default `gen_random_uuid()` |
| `user_id` | UUID | FK → users, NOT NULL |
| `code` | TEXT | UNIQUE, NOT NULL |
| `expires_at` | TIMESTAMPTZ | NOT NULL — 10-minute TTL |

No RLS — codes are looked up by code value, not tenant. Rows deleted after use or expiry.

#### `notification_preferences`

Per-user notification channel toggles.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | UUID | PK, default `gen_random_uuid()` |
| `tenant_id` | UUID | NOT NULL, RLS-protected |
| `user_id` | UUID | FK → users, UNIQUE |
| `telegram_enabled` | BOOLEAN | default true |
| `created_at` | TIMESTAMPTZ | default `now()` |
| `updated_at` | TIMESTAMPTZ | default `now()` |

RLS policy: `tenant_id = current_setting('app.current_tenant')::uuid`

### Modified Tables

#### `tasks`

Add column:

| Column | Type | Constraints |
|--------|------|-------------|
| `user_id` | UUID | FK → users, nullable |

This routes notifications to the specific user who triggered the task, not just the tenant.

### RLS Updates

Add `telegram_accounts` and `notification_preferences` to the RLS table list. `telegram_link_codes` does not use RLS.

---

## 2. Telegram Bot Integration

### Architecture

The Telegram bot runs as webhook handlers inside the existing FastAPI app. Telegram sends updates to `POST /api/telegram/webhook/{bot_token}`. Handlers reuse the same DB session, Celery tasks, and Redis pub/sub infrastructure.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | No | Bot token from @BotFather. If unset, all Telegram features disabled silently. |
| `TELEGRAM_WEBHOOK_BASE_URL` | No | Public URL for webhook registration (e.g., `https://app.example.com`). Required for webhook mode. |

### Files

- `api/src/telegram/__init__.py`
- `api/src/telegram/webhook.py` — FastAPI router, receives updates, dispatches to handlers
- `api/src/telegram/handlers.py` — Command handlers adapted from `core/src/agent/telegram_bot.py`
- `api/src/telegram/linking.py` — Account linking flow (generate code, verify deep link)
- `api/src/telegram/sender.py` — Outbound: text messages, inline keyboards, file delivery

### Webhook Setup

On FastAPI startup (in `lifespan`):
1. Check if `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_BASE_URL` are set
2. If yes: call Telegram `setWebhook` API to register `{base_url}/api/telegram/webhook/{token}`
3. If no: skip, log info message "Telegram bot disabled — no TELEGRAM_BOT_TOKEN"

### Account Linking Flow

1. User clicks "Connect Telegram" in web Settings page
2. Frontend calls `POST /api/telegram/link-code`
3. Backend generates a random 12-character code, stores in `telegram_link_codes` with 10-minute expiry, returns `{code, deep_link: "t.me/{bot_username}?start={code}"}`
4. User clicks the deep link → opens bot in Telegram
5. Bot receives `/start {code}` update via webhook
6. `linking.py` looks up code in `telegram_link_codes`:
   - If valid and not expired: create `telegram_accounts` row (with `chat_id` from the update), create default `notification_preferences` row, delete the code, reply "Linked to {email}"
   - If invalid/expired: reply "Invalid or expired code. Please try again from Settings."
7. Frontend polls `GET /api/telegram/status` to detect successful linking (returns `{linked: true/false, username, chat_id}`)

### Commands

All commands require the Telegram account to be linked (looked up by `chat_id`). Unlinked users get "Please link your account first — visit Settings in the web app."

| Command | Description | Implementation |
|---------|-------------|----------------|
| `/start <code>` | Account linking | Look up code, create telegram_account |
| `/help` | List available commands | Static text response |
| `/jobs` | Latest 10 jobs with scores | Query jobs table, format as list |
| `/top` | Jobs with fit >= 70 | Query jobs + analyses, filter by score |
| `/job <id>` | Job detail | Query job + analysis, inline buttons: `[Analyze] [Generate] [Apply]` |
| `/discover` | Trigger discovery | Create task, dispatch Celery `run_discovery` |
| `/search <query>` | Search for jobs | Create task, dispatch Celery `search_jobs` |
| `/generate <id>` | Generate docs | Create task, dispatch Celery `generate_docs`, send PDFs on completion |
| `/approve <ids>` | Bulk approve | Update application status, confirm |
| `/status` | Pipeline summary | Count by application status |
| `/unlink` | Disconnect account | Delete `telegram_accounts` row, confirm |

### Inline Keyboards

Job listings include callback buttons:

```
Senior ML Engineer @ Google (87%)
[View Details] [Generate Docs] [Approve]
```

Callback queries route through the webhook handler, parsed by callback data prefix (e.g., `job:42:analyze`).

### File Delivery

When `/generate` completes or user calls `/send <id>`:
1. Fetch PDF path from `applications.resume_path` / `applications.cover_letter_path`
2. Download bytes from MinIO via the existing storage client
3. Send via Telegram `send_document(chat_id=chat_id, document=bytes, filename="resume.pdf")`

### Rate Limiting

Inherit the CLI bot's 30-second cooldown on heavy commands (`/discover`, `/search`, `/generate`, `/apply`). Tracked per `chat_id` in Redis with TTL keys.

---

## 3. Notification Service

### Architecture

A dispatch module that Celery workers call after task events. Not a separate service — a function call within the worker process.

### Files

- `api/src/notifications/__init__.py`
- `api/src/notifications/dispatcher.py` — `notify(tenant_id, user_id, event_type, data)` function
- `api/src/notifications/formatters.py` — Format event data into human-readable Telegram messages

### Flow

1. Celery worker completes a task step
2. Calls `_publish_event(tenant_id, event_type, data)` — existing, for SSE (unchanged)
3. Calls `notify(tenant_id, user_id, event_type, data)`
4. `notify()` does:
   - Query `notification_preferences` for user — if no row, treat as defaults (telegram_enabled=true)
   - If `telegram_enabled` and user has a `telegram_accounts` row:
     - Format message via `formatters.py`
     - Send via `sender.py`
   - Fire-and-forget: catch all exceptions, log, don't block the worker

### Message Formats

| Event | Telegram Message |
|-------|-----------------|
| `task:completed` (scrape) | "Job scraped: **{title} @ {company}** — {location}" + `[View Job]` button |
| `task:completed` (analyze) | "Analysis done: **{title} @ {company}** — Fit: **{score}%** ({gap_count} gaps)" + `[View] [Generate]` buttons |
| `task:completed` (generate) | "Docs ready: **{title} @ {company}**" + auto-attach PDF files |
| `task:completed` (discover) | "Discovery found **{count} new jobs**. Top: {top_title} @ {top_company} ({top_score}%)" + `[View Jobs]` button |
| `task:failed` | "Task failed: {error}" |

### Delivery Guarantees

- Fire-and-forget — if Telegram API call fails (network error, bot blocked by user, rate limit), log the error and continue
- No retry queue — Telegram messages are ephemeral notifications, not critical data
- No message history stored in our DB — Telegram retains the chat

---

## 4. Global Task Panel (Web)

### Components

#### `web/src/components/layout/task-badge.tsx`

- Renders a lucide `Activity` icon in the icon rail (between nav items and Settings)
- Shows numeric badge when `tasks.length > 0`
- Badge hidden when no active tasks
- Brief pulse animation on new task events
- Clicking opens the task drawer

#### `web/src/components/layout/task-drawer.tsx`

Slide-out panel from the right edge of the screen.

**Running tasks section:**
- Type icon (briefcase for scrape, bar-chart for analyze, file-text for generate, compass for discover)
- Task name/description
- Animated progress bar (0-100%)
- Elapsed time since started

**Recent tasks section (last 10, past hour):**
- Status icon (green check for completed, red X for failed)
- Task name + timestamp
- Result summary (e.g., "Fit: 87%" for analysis, "12 jobs found" for discovery)
- Failed tasks show error in red
- Each row clickable — navigates to relevant page (e.g., job detail for completed scrape)

### Task Store Changes

Extend `web/src/stores/task-store.ts`:

```typescript
interface TaskState {
  tasks: RunningTask[];           // Active tasks (existing)
  recentTasks: CompletedTask[];   // Completed/failed (new, max 10)
  drawerOpen: boolean;            // Drawer visibility (new)
  // ... existing methods ...
  completeTask: (id, result) => void;  // Move from tasks → recentTasks
  failTask: (id, error) => void;       // Move from tasks → recentTasks
  toggleDrawer: () => void;
}
```

Auto-expire: recent tasks older than 1 hour are pruned on each state update.

### Hydration

On SSE reconnect or initial page load, fetch `GET /api/tasks?limit=10` to restore running/recent task state. This handles page refresh and navigation that may have missed SSE events.

---

## 5. Refresh Token Flow

### Backend

#### Token Configuration

| Token | Lifetime | Transport | Storage |
|-------|----------|-----------|---------|
| Access token | 15 minutes | JSON body (`BearerTransport`) | Frontend memory (Zustand) |
| Refresh token | 7 days | httpOnly cookie (`CookieTransport`) | Browser cookie jar |

#### Auth Backend Changes (`api/src/auth/backend.py`)

Add a second `AuthenticationBackend` for refresh tokens:

```python
cookie_transport = CookieTransport(
    cookie_name="refresh_token",
    cookie_httponly=True,
    cookie_secure=settings.cookie_secure,  # True in production, False for local HTTP dev
    cookie_samesite="lax",
    cookie_max_age=604800,    # 7 days
)

refresh_strategy = JWTStrategy(
    secret=settings.jwt_secret,
    lifetime_seconds=604800,
    token_audience=["fastapi-users:refresh"],  # Distinct from access tokens
)

refresh_backend = AuthenticationBackend(
    name="jwt-refresh",
    transport=cookie_transport,
    get_strategy=lambda: refresh_strategy,
)
```

#### Refresh Endpoint (`api/src/auth/refresh.py`)

`POST /api/auth/refresh`:
1. Read `refresh_token` from httpOnly cookie
2. Validate JWT (check signature, expiry, audience)
3. Load user from DB
4. If valid: return new access token in body + set new refresh cookie (rotation)
5. If invalid: return 401, clear the cookie

#### Login Change

`POST /api/auth/login` response:
- Body: `{"access_token": "...", "token_type": "bearer"}` (unchanged)
- Header: `Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Lax; Max-Age=604800; Path=/api/auth`

Cookie `Path=/api/auth` ensures it's only sent to auth endpoints, not every API call.

#### Logout Change

`POST /api/auth/logout`:
- Clears the refresh cookie: `Set-Cookie: refresh_token=; Max-Age=0; Path=/api/auth`

#### Access Token Lifetime

Reduce from current setting to 15 minutes: `jwt_lifetime_seconds=900` in config.

### Frontend

#### Axios Interceptor (`web/src/lib/api.ts`)

On 401 response:
1. If not already refreshing: call `POST /api/auth/refresh` (cookie sent automatically by browser)
2. If refresh succeeds: update auth store with new access token, retry the original request
3. If refresh fails (401): clear auth store, redirect to `/login`
4. Queue concurrent 401s during refresh — don't fire multiple refresh calls simultaneously

#### Silent Restore (`web/src/hooks/use-auth.ts`)

On app mount (before rendering protected routes):
1. Call `POST /api/auth/refresh`
2. If succeeds: set auth store, user stays logged in
3. If fails: user sees login page

This replaces the need for localStorage — the httpOnly cookie persists across page refreshes.

#### SSE Token Update

When access token is refreshed, the SSE EventSource needs to reconnect with the new token. The `useTaskStream` hook should watch the token in auth store and reconnect when it changes.

---

## 6. Mobile Responsive Layout

### Breakpoint Strategy

`md` (768px) is the pivot point. Below `md` = mobile layout, above = current desktop layout.

### Navigation

**Desktop (>= 768px):** Current icon rail (left sidebar, 52px collapsed, 200px on hover).

**Mobile (< 768px):** Fixed bottom tab bar with 5 items:

| Icon | Label | Route |
|------|-------|-------|
| LayoutDashboard | Home | `/dashboard` |
| Briefcase | Jobs | `/jobs` |
| Compass | Discover | `/discover` |
| Globe | Search | `/search` |
| Menu | More | Opens sheet with remaining items |

"More" sheet contains: Skills, Profile, Answers, Settings, Billing.

#### Files

- `web/src/components/layout/mobile-nav.tsx` — Bottom tab bar, only rendered below `md`
- `web/src/components/layout/icon-rail.tsx` — Add `hidden md:flex` to hide on mobile
- `web/src/components/layout/app-shell.tsx` — Conditionally render mobile-nav

### Task Badge (Mobile)

Moves into the top bar on mobile (since the icon rail is hidden). Same badge + drawer behavior, but drawer renders as a full-screen sheet on mobile.

### Content Layout Adjustments

| Page | Desktop | Mobile |
|------|---------|--------|
| **Dashboard** | 4 stats cards in row | 2x2 grid |
| **Job detail** | Two-column (tabs + action panel) | Single column stack, action panel below |
| **Profile** | Multi-section form | Full-width sections, fields stack vertically |
| **Skills** | Charts + tables side by side | Stacked, charts at reduced height |
| **Billing plans** | 3-column comparison | Vertical card stack |
| **Discovery** | Config cards in grid | Single column |
| **Settings** | Sections in card grid | Full-width stacked cards |

### Dialog/Drawer Behavior (Mobile)

- Task drawer → full-screen sheet
- Confirm dialogs → bottom sheet
- Discovery config editor → full-screen on mobile
- Job scrape dialog → bottom sheet

### Implementation Approach

All changes via Tailwind responsive utilities (`md:`, `lg:`, `hidden md:block`, etc.) and existing shadcn sheet/drawer components. No new dependencies needed.

---

## 7. E2E Tests with Playwright

### Setup

```
e2e/
├── playwright.config.ts    # Base URL, projects, timeouts
├── fixtures/
│   ├── auth.ts             # Register + login helper, stored auth state
│   ├── seed.ts             # Create test data via API
│   └── telegram-mock.ts    # Mock Telegram Bot API
├── tests/
│   ├── auth.spec.ts
│   ├── dashboard.spec.ts
│   ├── jobs.spec.ts
│   ├── discovery.spec.ts
│   ├── search.spec.ts
│   ├── profile.spec.ts
│   ├── answers.spec.ts
│   ├── skills.spec.ts
│   ├── settings.spec.ts
│   ├── billing.spec.ts
│   ├── task-panel.spec.ts
│   ├── telegram.spec.ts
│   └── mobile.spec.ts
└── package.json            # Playwright + dependencies
```

### Configuration

```typescript
// playwright.config.ts
export default defineConfig({
  testDir: './tests',
  baseURL: 'http://localhost:3000',
  use: { trace: 'on-first-retry' },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'mobile-safari', use: { ...devices['iPhone 13'] } },
  ],
});
```

### Test Fixtures

**Auth fixture (`fixtures/auth.ts`):**
- Registers a fresh user via `POST /api/auth/register`
- Logs in via `POST /api/auth/login`
- Stores auth state for reuse across tests in the same suite

**Seed fixture (`fixtures/seed.ts`):**
- Creates test tenant, user, jobs with analyses via direct API calls
- Called in `beforeAll` for suites that need data

**Telegram mock (`fixtures/telegram-mock.ts`):**
- Intercepts outbound calls to `api.telegram.org` via Playwright route interception (frontend) and a lightweight HTTP mock (backend webhook tests)
- Provides helpers to craft Telegram update payloads for simulating bot commands

### Test Suites (~44 tests)

#### Auth (`auth.spec.ts`)
1. Register new account — form submits, redirects to dashboard
2. Login with valid credentials — redirects to dashboard
3. Login with invalid credentials — shows error
4. Logout — redirects to login page
5. Refresh token — page refresh preserves session (no re-login)

#### Dashboard (`dashboard.spec.ts`)
6. Stats cards render with correct data
7. Quick scrape bar — submit URL, task starts, toast appears

#### Jobs (`jobs.spec.ts`)
8. Job list loads and displays entries
9. Search filters results by title/company
10. Sort toggles between asc/desc
11. Scrape dialog — enter URL, creates task
12. Job detail — tabs switch (Analysis/Description/Documents)
13. Delete job with confirmation dialog

#### Discovery (`discovery.spec.ts`)
14. Create search config
15. Toggle config active/inactive
16. Run All button triggers discovery task
17. Delete config

#### Search (`search.spec.ts`)
18. Search with query returns results

#### Profile (`profile.spec.ts`)
19. Edit profile fields (name, summary)
20. Add/remove experience entry via field array
21. JSON import populates form

#### Answers (`answers.spec.ts`)
22. Add new answer
23. Search filters answers
24. Bulk JSON import

#### Skills (`skills.spec.ts`)
25. Charts render (bar chart, line chart)
26. Gaps table displays data

#### Settings (`settings.spec.ts`)
27. Account info displays correctly
28. Theme toggle switches dark/light
29. Telegram link flow — generate code, shows deep link

#### Billing (`billing.spec.ts`)
30. Plan cards render (Free/Pro/Enterprise)
31. Usage chart displays

#### Task Panel (`task-panel.spec.ts`)
32. Badge appears when task is running
33. Drawer opens showing task progress
34. Completed task moves to recent section
35. Failed task shows error in red

#### Telegram (`telegram.spec.ts`)
36. Generate link code via API
37. Simulate `/start {code}` webhook — account linked
38. Simulate `/jobs` command — returns job list
39. Notification delivery — complete a task, verify Telegram API called with formatted message
40. Unlink account via `/unlink` command

#### Mobile (`mobile.spec.ts`)
41. Bottom nav renders at mobile viewport
42. Job detail stacks to single column
43. Task drawer becomes full-screen sheet
44. "More" menu opens remaining nav items

### Running Tests

```bash
# Install
cd e2e && npm install

# Run all (requires Docker stack running)
npx playwright test

# Run specific suite
npx playwright test tests/telegram.spec.ts

# Run with UI mode
npx playwright test --ui

# Mobile tests only
npx playwright test --project=mobile-safari
```

---

## 8. New API Endpoints Summary

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/telegram/webhook/{token}` | Telegram webhook receiver |
| `POST` | `/api/telegram/link-code` | Generate linking deep link |
| `GET` | `/api/telegram/status` | Check if Telegram is linked |
| `DELETE` | `/api/telegram/unlink` | Disconnect Telegram account |
| `GET` | `/api/notifications/preferences` | Get notification preferences |
| `PUT` | `/api/notifications/preferences` | Update notification preferences |
| `POST` | `/api/auth/refresh` | Refresh access token via cookie |

---

## 9. Docker / Environment Changes

### New Environment Variables

| Variable | Service | Required | Default |
|----------|---------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | api, worker | No | — (Telegram disabled if unset) |
| `TELEGRAM_WEBHOOK_BASE_URL` | api | No | — (required for webhook registration) |

### Docker Compose Updates

- Add `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_BASE_URL` to api service environment
- Worker also needs `TELEGRAM_BOT_TOKEN` for notification delivery via `sender.py`
- No new containers — bot runs inside the existing API service

---

## 10. Implementation Order

1. **Database migration** — New tables + tasks.user_id column
2. **Refresh token flow** — Backend + frontend (unblocks persistent sessions)
3. **Telegram bot webhook + linking** — Core bot infrastructure
4. **Telegram command handlers** — Adapt CLI commands for SaaS
5. **Notification service** — Dispatcher + formatters + Telegram delivery
6. **Global task panel** — Badge + drawer + store changes
7. **Mobile responsive** — Bottom nav + layout adjustments
8. **E2E tests** — All suites
