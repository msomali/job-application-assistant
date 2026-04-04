# Phase 3: React/Vite Frontend — Design Spec

**Date:** 2026-04-04
**Status:** Draft
**Parent spec:** `docs/superpowers/specs/2026-04-03-frontend-saas-design.md`
**Phase 2 backend:** 42 API endpoints implemented, all tests passing

## Scope

Full MVP — all 16 pages in one phase. The React SPA consumes the Phase 2 FastAPI backend.

## Tech Stack

| Layer | Choice | Version |
|-------|--------|---------|
| Framework | React + Vite | React 19, Vite 6 |
| UI components | shadcn/ui + Tailwind CSS | Latest |
| Data fetching | TanStack Query | v5 |
| Routing | React Router | v7 |
| Global state | Zustand | v5 |
| Forms | React Hook Form + Zod | RHF v7, Zod v3 |
| Charts | Recharts | v2 |
| API client | openapi-ts | Generated from FastAPI OpenAPI spec |
| Toasts | Sonner | Latest |
| Testing | Vitest + React Testing Library + MSW | Latest |

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| App shell | Icon rail sidebar (collapsed default, expand on hover) | Modern feel (Linear/Vercel style), maximizes content space |
| Default theme | Light (shadcn zinc) | Clean, professional. Dark mode toggle included |
| API client generation | openapi-ts | Type-safe, auto-generated from backend OpenAPI spec. Zero manual typing |
| State management | Zustand for auth/tasks, TanStack Query for server state | Clear separation — Zustand for client-only state, TQ for cache/sync |

## Project Structure

```
web/
├── public/
├── src/
│   ├── api/                    # openapi-ts generated client
│   │   ├── client.ts           # Configured axios instance (base URL, interceptors)
│   │   └── generated/          # Auto-generated types + request functions
│   ├── components/
│   │   ├── ui/                 # shadcn/ui primitives (button, card, input, etc.)
│   │   ├── layout/
│   │   │   ├── app-shell.tsx   # Icon rail + top bar + content area
│   │   │   ├── icon-rail.tsx   # Collapsed sidebar with hover expand
│   │   │   ├── top-bar.tsx     # Page title, task indicator, user menu
│   │   │   └── theme-toggle.tsx
│   │   ├── jobs/
│   │   │   ├── job-card.tsx    # Row in jobs list
│   │   │   ├── job-filters.tsx # Filter tabs + search + sort
│   │   │   ├── score-badge.tsx # Color-coded fit score
│   │   │   └── skill-tag.tsx   # Matched/gap skill pill
│   │   ├── profile/
│   │   │   ├── profile-form.tsx    # Multi-section form
│   │   │   ├── experience-editor.tsx
│   │   │   └── json-import.tsx
│   │   ├── skills/
│   │   │   ├── top-skills-chart.tsx
│   │   │   ├── gaps-table.tsx
│   │   │   └── trends-chart.tsx
│   │   ├── tasks/
│   │   │   ├── task-indicator.tsx   # Top bar running tasks badge
│   │   │   └── task-toast.tsx       # SSE-driven toast notifications
│   │   └── shared/
│   │       ├── query-state.tsx      # Loading/error/empty wrapper
│   │       ├── pagination.tsx
│   │       ├── confirm-dialog.tsx
│   │       └── error-boundary.tsx
│   ├── hooks/
│   │   ├── use-auth.ts         # Auth state + login/logout/register
│   │   ├── use-task-stream.ts  # SSE EventSource connection + reconnect
│   │   └── use-debounce.ts
│   ├── pages/
│   │   ├── auth/
│   │   │   ├── login.tsx
│   │   │   ├── register.tsx
│   │   │   └── forgot-password.tsx
│   │   ├── dashboard.tsx
│   │   ├── jobs/
│   │   │   ├── list.tsx
│   │   │   └── detail.tsx
│   │   ├── discover.tsx
│   │   ├── search.tsx
│   │   ├── skills.tsx
│   │   ├── profile.tsx
│   │   ├── answers.tsx
│   │   ├── settings.tsx
│   │   └── billing/
│   │       ├── overview.tsx
│   │       ├── plans.tsx
│   │       ├── usage.tsx
│   │       └── history.tsx
│   ├── stores/
│   │   ├── auth-store.ts       # JWT token, user info, isAuthenticated
│   │   └── task-store.ts       # Running tasks from SSE stream
│   ├── lib/
│   │   ├── utils.ts            # cn() helper, formatters
│   │   └── validators.ts       # Shared Zod schemas
│   ├── router.tsx              # React Router config with auth guard
│   ├── app.tsx                 # Providers: QueryClient, Router, ThemeProvider
│   └── main.tsx                # Entry point
├── index.html
├── tailwind.config.ts
├── tsconfig.json
├── vite.config.ts
├── vitest.config.ts
└── package.json
```

## App Shell

### Icon Rail Sidebar

- **Collapsed state** (default): 52px wide, icon-only buttons with tooltips
- **Expanded state** (on hover): 220px wide, icons + labels, smooth transition
- **Navigation items**: Dashboard, Jobs, Discover, Search, Skills, Profile, Answers (top section); Settings (bottom, pinned)
- **Active state**: Light blue background on current page icon
- **Logo**: "J" lettermark at top, links to dashboard

### Top Bar

- **Left**: Current page title (bold)
- **Right**: Task indicator badge (e.g., "2 tasks running" with spinner), plan badge ("Free plan"), user avatar with dropdown menu (Profile, Settings, Logout)

### Theme

- **Light default**: shadcn zinc light — white backgrounds, zinc-50 surfaces, zinc-200 borders
- **Dark mode**: shadcn zinc dark — toggled via top bar or settings
- **Accent color**: Blue-600 (`#2563eb`) for primary actions, links, active states
- **Score colors**: Green (80+), blue (60–79), amber (40–59), red (<40)

## Pages

### Auth Pages (`/login`, `/register`, `/forgot-password`)

- Centered card on plain background, no sidebar
- Login: email + password fields, "Sign in" button, Google/GitHub OAuth buttons, links to register and forgot-password
- Register: email + password + confirm password, creates tenant + user via `POST /api/auth/register`
- Forgot password: email field, sends reset link
- On success: redirect to `/dashboard`

### Dashboard (`/dashboard`)

- **Quick action bar**: URL input + "Scrape Job" button + "Run Discovery" button
- **Stats cards** (4-column grid): Total Jobs, Avg Fit Score (with progress bar), Docs Generated (breakdown), Top Skill Gap
- **Top Ranked Jobs** table: Top 5 by fit score, color-coded badges, click to navigate to detail

### Jobs List (`/jobs`)

- **Filter tabs**: All, High Fit (80+), Pending (no analysis), Applied — counts in parentheses
- **Search bar**: Debounced text search across title, company, location
- **Sort dropdown**: Score (default), Date, Company
- **Job rows**: Score badge, title, company/location/salary, skill tags (matched + gaps), time ago, chevron to detail
- **Inline states**: "Analyzing..." spinner for async tasks in progress
- **Pagination**: 20 per page, prev/next + page numbers

### Job Detail (`/jobs/:id`)

- **Breadcrumb**: Jobs → [Job Title]
- **Two-column layout**:
  - **Left** (flex-1): Header (title, company, location, salary, scrape date, original link), tabbed content:
    - **Analysis tab**: Score breakdown (base + adjustments = final), matched skills (green), gaps (amber), recommendation text
    - **Description tab**: Full job description markdown
    - **Documents tab**: List of generated PDFs with download links
  - **Right** (260px, sticky): Action buttons (Generate Resume, Generate Cover Letter, Re-analyze, Apply via Browser), generated docs list with download icons, status indicator

### Profile (`/profile`)

- **Multi-section form**: Contact info, Professional Summary, Work Experience (repeatable entries with add/remove), Education, Skills (tag input), Certifications, Projects
- **Toolbar**: Save, Import JSON, Export JSON buttons
- **Import modal**: Paste or upload JSON in `master_resume.json` format → validates → populates form
- **Auto-save indicator**: "Saved" / "Unsaved changes" in toolbar

### Discover (`/discover`)

- **Config cards**: Grid of search config cards — name, type (search query / career page), config details, last run date, active/inactive toggle
- **CRUD**: Add Config button → modal form. Edit/delete on each card
- **Run All button**: Triggers `POST /api/discovery/run`, shows SSE-driven progress
- **Results feed**: Newly discovered jobs appear in real-time below configs as SSE events arrive

### Search (`/search`)

- **Search bar**: Query input + source toggle (Indeed / LinkedIn)
- **Filters**: Location, salary range, remote/hybrid/onsite
- **Results**: Similar layout to jobs list, but with "Save & Analyze" button per result
- **Save action**: Scrapes full job details → adds to jobs list → triggers analysis

### Skills (`/skills`)

- **Top Skills**: Horizontal bar chart (Recharts) — most requested skills across analyzed jobs
- **Skill Gaps**: Table with skill name, frequency in job listings, your proficiency indicator
- **Trends**: Line chart showing skill demand over time (by week/month)
- **Roles**: Pie/donut chart showing skills grouped by role category

### Answers (`/answers`)

- **List view**: Searchable, sortable table — question, answer (truncated), category, times used, last used
- **Add/Edit**: Modal with question + answer textarea + category select
- **Bulk import**: Upload JSON button → validates → imports with duplicate detection
- **Stats card**: Total answers, categories breakdown, fuzzy match hit rate

### Settings (`/settings`)

- **Sections**: Account (email, change password), Notifications (email preferences), Appearance (theme toggle, density), API Keys (display/regenerate)
- **Team section** (admin only): Invite user, list members with role badges, change roles, remove members

### Billing (`/billing`, `/billing/plans`, `/billing/usage`, `/billing/history`)

- **Overview**: Current plan card, usage meters (scrapes, analyses, generations vs limits), next billing date
- **Plans**: Comparison table (Free / Pro / Enterprise), feature checklist, upgrade CTA
- **Usage**: Detailed breakdown with daily/weekly charts, cost projections
- **History**: Invoice table with date, amount, status, download receipt
- All billing pages are UI-complete stubs — no real Stripe integration in Phase 3

## Data Flow

### API Client

- **openapi-ts**: Generate TypeScript client from FastAPI's `/openapi.json`
- **Axios instance**: Base URL from env var, request interceptor adds JWT `Authorization` header
- **Response interceptor**: On 401 → attempt token refresh → retry original request. On refresh failure → clear auth store → redirect to `/login`

### TanStack Query

- **Query keys**: Structured as `[resource, ...params]` — e.g., `['jobs', { page, sort, filter }]`, `['job', jobId]`, `['profile']`
- **Stale times**: Jobs list 30s, profile 5min, skills 2min, billing 10min
- **Mutations**: Optimistic updates for delete operations (remove from cache immediately, rollback on error). Invalidate related queries on success
- **Prefetching**: Prefetch job detail on row hover

### SSE (Server-Sent Events)

- **`useTaskStream` hook**: Opens EventSource to `/api/tasks/stream`, parses SSE events, updates Zustand task store
- **Auto-reconnect**: Exponential backoff (1s, 2s, 4s, max 30s) on disconnect
- **Event handling**:
  - `task:started` → add to task store, show toast
  - `task:progress` → update progress in store
  - `task:completed` → remove from store, success toast, invalidate relevant queries (e.g., scrape complete → invalidate jobs list)
  - `task:failed` → remove from store, error toast with message
- **Task indicator**: Top bar badge shows count of running tasks from store

### Auth Flow

- **JWT storage**: Access token in Zustand store (memory-only, lost on refresh). On page load, attempt silent refresh to restore session
- **Login**: `POST /api/auth/jwt/login` → store access token in Zustand → redirect to dashboard
- **Auth guard**: React Router loader checks `isAuthenticated` in auth store → redirect to `/login` if false
- **Token refresh**: Axios interceptor handles 401 → `POST /api/auth/jwt/login` with stored credentials is not viable. For v1, access token lives in memory only; user re-logs on page refresh. Add refresh token flow in a follow-up if needed

## Error Handling

### Global Error Boundary

- Wraps entire app in `<ErrorBoundary>` — catches unhandled React errors
- Fallback UI: "Something went wrong" with error details (dev only) and "Reload" button

### Per-Page Query States

- Shared `<QueryState>` component wraps every page's main query
- **Loading**: Skeleton placeholders matching page layout
- **Error**: Error message + "Retry" button
- **Empty**: Contextual empty state (e.g., "No jobs yet. Paste a URL above to get started.")

### Toast Notifications

- **Sonner** for toast notifications
- Mutation success: "Job scraped successfully", "Resume generated"
- Mutation error: "Failed to scrape job: [error message]"
- SSE task events: task completion/failure toasts

### Form Validation

- **Client-side**: Zod schemas validate before submission, errors shown inline per field
- **Server-side 422**: Map `detail[].loc` back to form field names, show server errors inline
- **Network errors**: Generic toast notification

### Network Resilience

- **GET requests**: TanStack Query auto-retry 3x with exponential backoff
- **Mutations**: No auto-retry (user must explicitly retry)
- **Offline**: No special offline support in v1 — standard error handling applies

## Testing Strategy

### Unit Tests (Vitest)

- Zod validation schemas
- Utility functions (formatters, score color logic)
- Zustand store logic (auth, tasks)

### Component Tests (Vitest + React Testing Library)

- Individual components: render, user interactions, state changes
- Query state variants: loading, error, empty, populated
- Form components: validation, submission, error display

### Integration Tests (MSW)

- Full page flows with mocked API responses
- Auth flow: login → redirect → authenticated page
- Job flow: scrape → list updates → detail view
- MSW handlers mirror the real API contract

### E2E Tests

- Deferred to Phase 4 (Playwright against real backend)

### Coverage Target

- 70%+ on components and hooks
- 90%+ on utility functions and validators

## Build & Dev

### Development

```bash
# Install dependencies
cd web && npm install

# Generate API client from running backend
npm run generate-api    # openapi-ts from http://localhost:8000/openapi.json

# Start dev server
npm run dev             # Vite dev server on :3000, proxies /api to :8000
```

### Production Build

```bash
npm run build           # Outputs to web/dist/
```

### Docker

```dockerfile
# Multi-stage: Node build → nginx serve
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

### Vite Config

- **Proxy**: `/api` → `http://localhost:8000` in dev mode
- **Env vars**: `VITE_API_URL` for production API base URL
- **Aliases**: `@/` → `src/` for clean imports

## Non-Goals (Phase 3)

- Real payment processing (Stripe integration deferred)
- Browser automation / computer use for applications
- Telegram bot integration
- Offline support / PWA
- i18n / localization
- Mobile-specific responsive design (desktop-first, basic mobile works)
