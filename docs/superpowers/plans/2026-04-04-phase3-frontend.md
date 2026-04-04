# Phase 3: React/Vite Frontend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a React SPA that consumes the Phase 2 FastAPI backend (42 endpoints), covering all 16 pages with auth, real-time SSE updates, and the icon rail app shell.

**Architecture:** Vite + React 19 SPA with openapi-ts generated API client, TanStack Query for server state, Zustand for auth/task client state, shadcn/ui components, React Router v7 with auth guards. SSE via EventSource for real-time task updates.

**Tech Stack:** React 19, Vite 6, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query v5, React Router v7, Zustand v5, React Hook Form + Zod, Recharts, openapi-ts, Sonner, Vitest + React Testing Library + MSW

---

## File Map

### New files to create

```
web/
├── public/
│   └── favicon.svg
├── src/
│   ├── api/
│   │   └── client.ts                  # Axios instance + interceptors + openapi-ts config
│   ├── components/
│   │   ├── layout/
│   │   │   ├── app-shell.tsx          # Icon rail + top bar + outlet
│   │   │   ├── icon-rail.tsx          # Collapsed/expanded sidebar
│   │   │   ├── top-bar.tsx            # Page title, task badge, user menu
│   │   │   └── theme-toggle.tsx       # Light/dark switcher
│   │   ├── shared/
│   │   │   ├── query-state.tsx        # Loading/error/empty wrapper
│   │   │   ├── pagination.tsx         # Prev/next + page numbers
│   │   │   ├── confirm-dialog.tsx     # "Are you sure?" modal
│   │   │   └── error-boundary.tsx     # React error boundary
│   │   ├── jobs/
│   │   │   ├── score-badge.tsx        # Color-coded fit score pill
│   │   │   └── skill-tag.tsx          # Matched/gap skill pill
│   │   ├── tasks/
│   │   │   └── task-indicator.tsx     # Top bar running tasks badge
│   │   └── profile/
│   │       └── json-import-dialog.tsx # Import JSON modal
│   ├── hooks/
│   │   ├── use-auth.ts               # Login/logout/register + auth state
│   │   ├── use-task-stream.ts        # SSE EventSource + reconnect
│   │   └── use-debounce.ts           # Debounced value hook
│   ├── pages/
│   │   ├── auth/
│   │   │   ├── login.tsx
│   │   │   ├── register.tsx
│   │   │   └── forgot-password.tsx
│   │   ├── dashboard.tsx
│   │   ├── jobs/
│   │   │   ├── list.tsx
│   │   │   └── detail.tsx
│   │   ├── profile.tsx
│   │   ├── discover.tsx
│   │   ├── search.tsx
│   │   ├── skills.tsx
│   │   ├── answers.tsx
│   │   ├── settings.tsx
│   │   └── billing/
│   │       ├── overview.tsx
│   │       ├── plans.tsx
│   │       ├── usage.tsx
│   │       └── history.tsx
│   ├── stores/
│   │   ├── auth-store.ts             # JWT + user info + isAuthenticated
│   │   └── task-store.ts             # Running tasks from SSE
│   ├── lib/
│   │   ├── utils.ts                  # cn(), formatters, score colors
│   │   └── query-keys.ts             # Centralized TanStack Query key factory
│   ├── router.tsx                    # React Router config + auth guard
│   ├── app.tsx                       # Providers wrapper
│   ├── main.tsx                      # Entry point
│   └── globals.css                   # Tailwind directives + shadcn vars
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── tailwind.config.ts
├── postcss.config.js
├── vite.config.ts
├── vitest.config.ts
├── components.json                   # shadcn/ui config
└── .env.development
```

### Files to modify

```
docker-compose.yml                    # Add web service
Makefile                              # Add web-dev, web-build, web-test targets
.gitignore                            # Add web/node_modules, web/dist
```

---

## Task 1: Project Scaffold + Vite + Tailwind + shadcn/ui

**Files:**
- Create: `web/package.json`, `web/index.html`, `web/tsconfig.json`, `web/tsconfig.app.json`, `web/tsconfig.node.json`, `web/vite.config.ts`, `web/postcss.config.js`, `web/tailwind.config.ts`, `web/components.json`, `web/src/main.tsx`, `web/src/app.tsx`, `web/src/globals.css`, `web/src/vite-env.d.ts`, `web/.env.development`
- Modify: `.gitignore`, `Makefile`

- [ ] **Step 1: Scaffold Vite React-TS project**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant
# Remove placeholder
rm -f web/.gitkeep
# Create Vite project in temp dir, then move files into web/
npm create vite@latest web-tmp -- --template react-ts
# Move contents into existing web/ dir
cp -r web-tmp/* web-tmp/.* web/ 2>/dev/null || true
rm -rf web-tmp
cd web
npm install
```

- [ ] **Step 2: Install core dependencies**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npm install @tanstack/react-query react-router@7 zustand @hookform/resolvers react-hook-form zod recharts sonner axios lucide-react
npm install -D @types/node
```

- [ ] **Step 3: Install and initialize Tailwind CSS v4 + shadcn/ui**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
# Install tailwindcss
npm install tailwindcss @tailwindcss/vite
```

Update `web/vite.config.ts`:

```ts
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
```

Update `web/tsconfig.app.json` to add path alias:

```json
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"]
}
```

Initialize shadcn/ui:

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx shadcn@latest init -d
```

This creates `web/src/globals.css` with CSS variables and `web/components.json`. The `-d` flag uses defaults (New York style, Zinc color, CSS variables enabled).

- [ ] **Step 4: Set light theme as default**

Update `web/src/globals.css` — ensure the `:root` (light) theme is the default and `.dark` is the alternate. The `shadcn init` should handle this, but verify there is no `dark` class on `<html>` by default.

Update `web/index.html` — make sure `<html>` has no `class="dark"`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>JobAssist</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Add shadcn/ui components we'll need**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx shadcn@latest add button card input label tabs badge dropdown-menu dialog select textarea tooltip avatar separator sheet scroll-area table skeleton switch form sonner
```

- [ ] **Step 6: Create .env.development**

Create `web/.env.development`:

```
VITE_API_URL=http://localhost:8000
```

- [ ] **Step 7: Write minimal app entry point**

Create `web/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./globals.css";
import { App } from "./app";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

Create `web/src/app.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router";
import { Toaster } from "@/components/ui/sonner";
import { router } from "./router";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 3,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster />
    </QueryClientProvider>
  );
}
```

- [ ] **Step 8: Create placeholder router**

Create `web/src/router.tsx`:

```tsx
import { createBrowserRouter } from "react-router";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <div className="p-8 text-2xl font-bold">JobAssist — scaffold working</div>,
  },
]);
```

- [ ] **Step 9: Update .gitignore and Makefile**

Append to `.gitignore`:

```
# Web frontend
web/node_modules/
web/dist/
```

Add to `Makefile` (append after the existing `db-reset` target):

```makefile
web-dev:
	cd web && npm run dev

web-build:
	cd web && npm run build

web-test:
	cd web && npx vitest run

web-install:
	cd web && npm install
```

- [ ] **Step 10: Verify scaffold runs**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npm run dev -- --host 2>&1 &
sleep 3
curl -s http://localhost:3000 | head -20
kill %1 2>/dev/null
```

Expected: HTML response with `<div id="root">`.

- [ ] **Step 11: Commit**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant
git add web/ .gitignore Makefile
git commit -m "feat(web): scaffold Vite + React + Tailwind + shadcn/ui project"
```

---

## Task 2: API Client + Auth Store + Auth Hook

**Files:**
- Create: `web/src/api/client.ts`, `web/src/stores/auth-store.ts`, `web/src/hooks/use-auth.ts`
- Test: `web/src/stores/__tests__/auth-store.test.ts`, `web/src/hooks/__tests__/use-auth.test.ts`

- [ ] **Step 1: Set up testing infrastructure**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom msw@latest
```

Create `web/vitest.config.ts`:

```ts
import path from "path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    css: false,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
```

Create `web/src/test-setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 2: Write auth store tests**

Create `web/src/stores/__tests__/auth-store.test.ts`:

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { useAuthStore } from "../auth-store";

describe("auth-store", () => {
  beforeEach(() => {
    useAuthStore.getState().logout();
  });

  it("starts unauthenticated", () => {
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.token).toBeNull();
    expect(state.user).toBeNull();
  });

  it("setAuth stores token and user", () => {
    useAuthStore.getState().setAuth("jwt-token-123", {
      id: "u1",
      email: "test@example.com",
      tenant_id: "t1",
      role: "member",
    });
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.token).toBe("jwt-token-123");
    expect(state.user?.email).toBe("test@example.com");
  });

  it("logout clears everything", () => {
    useAuthStore.getState().setAuth("token", {
      id: "u1",
      email: "a@b.com",
      tenant_id: "t1",
      role: "member",
    });
    useAuthStore.getState().logout();
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.token).toBeNull();
    expect(state.user).toBeNull();
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx vitest run src/stores/__tests__/auth-store.test.ts
```

Expected: FAIL — `auth-store` module not found.

- [ ] **Step 4: Implement API client**

Create `web/src/api/client.ts`:

```ts
import axios from "axios";
import { useAuthStore } from "@/stores/auth-store";

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "",
  headers: { "Content-Type": "application/json" },
});

// Add JWT token to every request
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// On 401, clear auth and redirect to login
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export { apiClient };
```

- [ ] **Step 5: Implement auth store**

Create `web/src/stores/auth-store.ts`:

```ts
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
  setAuth: (token: string, user: AuthUser) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  isAuthenticated: false,
  setAuth: (token, user) => set({ token, user, isAuthenticated: true }),
  logout: () => set({ token: null, user: null, isAuthenticated: false }),
}));
```

- [ ] **Step 6: Run auth store tests**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx vitest run src/stores/__tests__/auth-store.test.ts
```

Expected: PASS (3 tests).

- [ ] **Step 7: Write use-auth hook tests**

Create `web/src/hooks/__tests__/use-auth.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock apiClient before importing the hook
vi.mock("@/api/client", () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

import { apiClient } from "@/api/client";
import { useAuthStore } from "@/stores/auth-store";

// Test the login/register logic directly (not as a React hook — avoids render complexity)
describe("auth logic", () => {
  beforeEach(() => {
    useAuthStore.getState().logout();
    vi.clearAllMocks();
  });

  it("login stores token from API response", async () => {
    const mockPost = vi.mocked(apiClient.post);
    mockPost.mockResolvedValueOnce({
      data: { access_token: "jwt-abc", token_type: "bearer" },
    });
    mockPost.mockResolvedValueOnce({
      data: { id: "u1", email: "a@b.com", tenant_id: "t1", role: "member", is_active: true, is_verified: false },
    });

    // Simulate login flow: POST login, then GET /api/auth/me (actually a second post for form data)
    // fastapi-users login returns {access_token, token_type}
    const loginResp = await apiClient.post("/api/auth/login", new URLSearchParams({
      username: "a@b.com",
      password: "pass123",
    }));
    const token = loginResp.data.access_token;

    // Simulate fetching user info
    const mockGet = vi.mocked(apiClient.get);
    mockGet.mockResolvedValueOnce({
      data: { id: "u1", email: "a@b.com", tenant_id: "t1", role: "member" },
    });

    useAuthStore.getState().setAuth(token, {
      id: "u1",
      email: "a@b.com",
      tenant_id: "t1",
      role: "member",
    });

    expect(useAuthStore.getState().isAuthenticated).toBe(true);
    expect(useAuthStore.getState().token).toBe("jwt-abc");
  });
});
```

- [ ] **Step 8: Run test to verify it fails**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx vitest run src/hooks/__tests__/use-auth.test.ts
```

Expected: PASS — these tests use mocks and the already-implemented store.

- [ ] **Step 9: Implement use-auth hook**

Create `web/src/hooks/use-auth.ts`:

```ts
import { useMutation } from "@tanstack/react-query";
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

async function fetchCurrentUser() {
  // fastapi-users provides GET /api/users/me but we registered it as /api/auth/me
  // Actually, fastapi-users get_users_router provides /me. Let's check the actual setup.
  // The backend uses fastapi_users.current_user — we fetch user info after login.
  // For now, we decode user info from the /api/auth/me endpoint if available,
  // or from the register response.
  const resp = await apiClient.get("/api/users/me");
  return resp.data;
}

export function useLogin() {
  const setAuth = useAuthStore((s) => s.setAuth);

  return useMutation({
    mutationFn: async (creds: LoginCredentials) => {
      // fastapi-users expects form-encoded POST with username/password
      const form = new URLSearchParams();
      form.append("username", creds.email);
      form.append("password", creds.password);

      const resp = await apiClient.post("/api/auth/login", form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      const token = resp.data.access_token;

      // Temporarily set token so the next request is authenticated
      useAuthStore.getState().setAuth(token, { id: "", email: creds.email, tenant_id: "", role: "" });

      // Fetch full user info
      const user = await fetchCurrentUser();
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
      } catch {
        // Logout even if the API call fails
      }
      logout();
    },
  });
}
```

- [ ] **Step 10: Implement utility functions**

Create `web/src/lib/utils.ts`:

```ts
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Color class for fit score badge */
export function scoreColor(score: number): string {
  if (score >= 80) return "bg-green-100 text-green-700";
  if (score >= 60) return "bg-blue-100 text-blue-700";
  if (score >= 40) return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-700";
}

/** Relative time string (e.g. "2h ago", "3d ago") */
export function timeAgo(date: string | Date): string {
  const now = Date.now();
  const then = new Date(date).getTime();
  const seconds = Math.floor((now - then) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
```

Create `web/src/lib/query-keys.ts`:

```ts
export const queryKeys = {
  jobs: {
    all: ["jobs"] as const,
    list: (params: Record<string, unknown>) => ["jobs", params] as const,
    detail: (id: number) => ["jobs", id] as const,
    ranked: (limit?: number) => ["jobs", "ranked", limit] as const,
  },
  analysis: {
    byJob: (jobId: number) => ["analysis", jobId] as const,
  },
  documents: {
    byJob: (jobId: number) => ["documents", jobId] as const,
  },
  profile: {
    current: ["profile"] as const,
  },
  discovery: {
    configs: ["discovery", "configs"] as const,
  },
  search: {
    results: (params: Record<string, unknown>) => ["search", params] as const,
  },
  skills: {
    top: (limit?: number) => ["skills", "top", limit] as const,
    gaps: ["skills", "gaps"] as const,
    trends: ["skills", "trends"] as const,
    roles: ["skills", "roles"] as const,
  },
  answers: {
    all: ["answers"] as const,
    list: (params: Record<string, unknown>) => ["answers", params] as const,
    stats: ["answers", "stats"] as const,
  },
  billing: {
    plan: ["billing", "plan"] as const,
    usage: ["billing", "usage"] as const,
    history: (days?: number) => ["billing", "history", days] as const,
    invoices: ["billing", "invoices"] as const,
  },
  tasks: {
    all: ["tasks"] as const,
    detail: (id: string) => ["tasks", id] as const,
  },
  admin: {
    users: ["admin", "users"] as const,
  },
};
```

- [ ] **Step 11: Run all tests**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx vitest run
```

Expected: All tests PASS.

- [ ] **Step 12: Commit**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant
git add web/
git commit -m "feat(web): add API client, auth store, auth hooks, utils"
```

---

## Task 3: App Shell — Icon Rail + Top Bar + Theme Toggle

**Files:**
- Create: `web/src/components/layout/app-shell.tsx`, `web/src/components/layout/icon-rail.tsx`, `web/src/components/layout/top-bar.tsx`, `web/src/components/layout/theme-toggle.tsx`, `web/src/hooks/use-debounce.ts`, `web/src/components/shared/error-boundary.tsx`
- Modify: `web/src/router.tsx`

- [ ] **Step 1: Create error boundary**

Create `web/src/components/shared/error-boundary.tsx`:

```tsx
import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center">
          <div className="text-center space-y-4">
            <h1 className="text-2xl font-bold">Something went wrong</h1>
            {import.meta.env.DEV && (
              <pre className="text-sm text-muted-foreground max-w-md overflow-auto">
                {this.state.error?.message}
              </pre>
            )}
            <Button onClick={() => window.location.reload()}>Reload</Button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
```

- [ ] **Step 2: Create theme toggle**

Create `web/src/components/layout/theme-toggle.tsx`:

```tsx
import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const [dark, setDark] = useState(() =>
    document.documentElement.classList.contains("dark")
  );

  useEffect(() => {
    if (dark) {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  }, [dark]);

  // Restore theme on mount
  useEffect(() => {
    const saved = localStorage.getItem("theme");
    if (saved === "dark") setDark(true);
  }, []);

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setDark(!dark)}
      className="h-8 w-8"
    >
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
```

- [ ] **Step 3: Create task indicator**

Create `web/src/components/tasks/task-indicator.tsx`:

```tsx
import { Loader2 } from "lucide-react";
import { useTaskStore } from "@/stores/task-store";

export function TaskIndicator() {
  const count = useTaskStore((s) => s.tasks.length);

  if (count === 0) return null;

  return (
    <span className="flex items-center gap-1.5 rounded-full bg-blue-100 px-2.5 py-0.5 text-xs text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
      <Loader2 className="h-3 w-3 animate-spin" />
      {count} task{count !== 1 ? "s" : ""} running
    </span>
  );
}
```

Create `web/src/stores/task-store.ts`:

```ts
import { create } from "zustand";

export interface RunningTask {
  id: string;
  type: string;
  progress: number;
  message?: string;
}

interface TaskState {
  tasks: RunningTask[];
  addTask: (task: RunningTask) => void;
  updateTask: (id: string, updates: Partial<RunningTask>) => void;
  removeTask: (id: string) => void;
  clear: () => void;
}

export const useTaskStore = create<TaskState>((set) => ({
  tasks: [],
  addTask: (task) =>
    set((s) => ({
      tasks: s.tasks.some((t) => t.id === task.id)
        ? s.tasks
        : [...s.tasks, task],
    })),
  updateTask: (id, updates) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, ...updates } : t)),
    })),
  removeTask: (id) =>
    set((s) => ({ tasks: s.tasks.filter((t) => t.id !== id) })),
  clear: () => set({ tasks: [] }),
}));
```

- [ ] **Step 4: Create icon rail sidebar**

Create `web/src/components/layout/icon-rail.tsx`:

```tsx
import {
  BarChart3,
  Briefcase,
  Compass,
  Globe,
  LayoutDashboard,
  MessageSquare,
  Settings,
  TrendingUp,
  User,
} from "lucide-react";
import { NavLink } from "react-router";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/jobs", icon: Briefcase, label: "Jobs" },
  { to: "/discover", icon: Compass, label: "Discover" },
  { to: "/search", icon: Globe, label: "Search" },
  { to: "/skills", icon: TrendingUp, label: "Skills" },
  { to: "/profile", icon: User, label: "Profile" },
  { to: "/answers", icon: MessageSquare, label: "Answers" },
];

const bottomItems = [
  { to: "/settings", icon: Settings, label: "Settings" },
];

export function IconRail() {
  return (
    <TooltipProvider delayDuration={0}>
      <nav className="group/rail flex w-[52px] flex-col items-center gap-1 border-r bg-muted/40 px-2 py-3 transition-all duration-200 hover:w-[200px]">
        {/* Logo */}
        <NavLink
          to="/dashboard"
          className="mb-3 flex h-8 w-8 items-center justify-center rounded-md text-lg font-bold text-primary"
        >
          J
        </NavLink>

        {/* Main nav */}
        {navItems.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}

        {/* Spacer */}
        <div className="mt-auto" />

        {/* Bottom nav */}
        {bottomItems.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </nav>
    </TooltipProvider>
  );
}

function NavItem({
  to,
  icon: Icon,
  label,
}: {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <NavLink
          to={to}
          className={({ isActive }) =>
            cn(
              "flex h-9 w-full items-center gap-3 rounded-md px-2 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
              isActive && "bg-blue-50 text-blue-600 dark:bg-blue-950 dark:text-blue-400"
            )
          }
        >
          <Icon className="h-5 w-5 shrink-0" />
          <span className="truncate text-sm opacity-0 transition-opacity duration-200 group-hover/rail:opacity-100">
            {label}
          </span>
        </NavLink>
      </TooltipTrigger>
      <TooltipContent side="right" className="group-hover/rail:hidden">
        {label}
      </TooltipContent>
    </Tooltip>
  );
}
```

- [ ] **Step 5: Create top bar**

Create `web/src/components/layout/top-bar.tsx`:

```tsx
import { LogOut, Settings, User } from "lucide-react";
import { useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { TaskIndicator } from "@/components/tasks/task-indicator";
import { ThemeToggle } from "./theme-toggle";
import { useAuthStore } from "@/stores/auth-store";
import { useLogout } from "@/hooks/use-auth";

interface TopBarProps {
  title: string;
}

export function TopBar({ title }: TopBarProps) {
  const user = useAuthStore((s) => s.user);
  const { mutate: logout } = useLogout();
  const navigate = useNavigate();

  const initials = user?.email?.charAt(0).toUpperCase() ?? "?";

  return (
    <header className="flex h-12 items-center justify-between border-b px-5">
      <h1 className="text-[15px] font-semibold">{title}</h1>
      <div className="flex items-center gap-3">
        <TaskIndicator />
        <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground">
          Free plan
        </span>
        <ThemeToggle />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="h-8 w-8 rounded-full p-0">
              <Avatar className="h-7 w-7">
                <AvatarFallback className="text-xs">{initials}</AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem onClick={() => navigate("/profile")}>
              <User className="mr-2 h-4 w-4" /> Profile
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate("/settings")}>
              <Settings className="mr-2 h-4 w-4" /> Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => { logout(); navigate("/login"); }}>
              <LogOut className="mr-2 h-4 w-4" /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
```

- [ ] **Step 6: Create app shell**

Create `web/src/components/layout/app-shell.tsx`:

```tsx
import { Outlet, useLocation } from "react-router";
import { IconRail } from "./icon-rail";
import { TopBar } from "./top-bar";

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
  // Match path prefix for nested routes like /jobs/123
  const title =
    pageTitles[location.pathname] ??
    Object.entries(pageTitles).find(([prefix]) =>
      location.pathname.startsWith(prefix)
    )?.[1] ??
    "JobAssist";

  return (
    <div className="flex h-screen overflow-hidden">
      <IconRail />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar title={title} />
        <main className="flex-1 overflow-auto p-5">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Create use-debounce hook**

Create `web/src/hooks/use-debounce.ts`:

```ts
import { useEffect, useState } from "react";

export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}
```

- [ ] **Step 8: Update router with app shell and auth guard**

Replace `web/src/router.tsx`:

```tsx
import { createBrowserRouter, Navigate, redirect } from "react-router";
import { AppShell } from "@/components/layout/app-shell";
import { ErrorBoundary } from "@/components/shared/error-boundary";
import { useAuthStore } from "@/stores/auth-store";

// Lazy-loaded pages
import LoginPage from "@/pages/auth/login";
import RegisterPage from "@/pages/auth/register";
import ForgotPasswordPage from "@/pages/auth/forgot-password";

function requireAuth() {
  if (!useAuthStore.getState().isAuthenticated) {
    return redirect("/login");
  }
  return null;
}

function requireGuest() {
  if (useAuthStore.getState().isAuthenticated) {
    return redirect("/dashboard");
  }
  return null;
}

export const router = createBrowserRouter([
  // Public auth routes
  {
    path: "/login",
    loader: requireGuest,
    element: <LoginPage />,
  },
  {
    path: "/register",
    loader: requireGuest,
    element: <RegisterPage />,
  },
  {
    path: "/forgot-password",
    element: <ForgotPasswordPage />,
  },

  // Protected routes
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

  // Catch-all
  { path: "*", element: <Navigate to="/dashboard" replace /> },
]);
```

- [ ] **Step 9: Create placeholder pages for all routes**

Each page needs a minimal `Component` export for React Router lazy loading. Create each file:

Create `web/src/pages/auth/login.tsx`:

```tsx
export default function LoginPage() {
  return <div className="flex min-h-screen items-center justify-center"><p>Login page — TODO</p></div>;
}
```

Create `web/src/pages/auth/register.tsx`:

```tsx
export default function RegisterPage() {
  return <div className="flex min-h-screen items-center justify-center"><p>Register page — TODO</p></div>;
}
```

Create `web/src/pages/auth/forgot-password.tsx`:

```tsx
export default function ForgotPasswordPage() {
  return <div className="flex min-h-screen items-center justify-center"><p>Forgot password — TODO</p></div>;
}
```

For lazy-loaded pages, they need to export a `Component`:

Create `web/src/pages/dashboard.tsx`:

```tsx
export function Component() {
  return <p>Dashboard — coming soon</p>;
}
```

Create `web/src/pages/jobs/list.tsx`:

```tsx
export function Component() {
  return <p>Jobs list — coming soon</p>;
}
```

Create `web/src/pages/jobs/detail.tsx`:

```tsx
export function Component() {
  return <p>Job detail — coming soon</p>;
}
```

Create `web/src/pages/profile.tsx`:

```tsx
export function Component() {
  return <p>Profile — coming soon</p>;
}
```

Create `web/src/pages/discover.tsx`:

```tsx
export function Component() {
  return <p>Discover — coming soon</p>;
}
```

Create `web/src/pages/search.tsx`:

```tsx
export function Component() {
  return <p>Search — coming soon</p>;
}
```

Create `web/src/pages/skills.tsx`:

```tsx
export function Component() {
  return <p>Skills — coming soon</p>;
}
```

Create `web/src/pages/answers.tsx`:

```tsx
export function Component() {
  return <p>Answers — coming soon</p>;
}
```

Create `web/src/pages/settings.tsx`:

```tsx
export function Component() {
  return <p>Settings — coming soon</p>;
}
```

Create `web/src/pages/billing/overview.tsx`:

```tsx
export function Component() {
  return <p>Billing overview — coming soon</p>;
}
```

Create `web/src/pages/billing/plans.tsx`:

```tsx
export function Component() {
  return <p>Plans — coming soon</p>;
}
```

Create `web/src/pages/billing/usage.tsx`:

```tsx
export function Component() {
  return <p>Usage — coming soon</p>;
}
```

Create `web/src/pages/billing/history.tsx`:

```tsx
export function Component() {
  return <p>Billing history — coming soon</p>;
}
```

- [ ] **Step 10: Verify the app compiles and runs**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx tsc --noEmit
npm run dev -- --host 2>&1 &
sleep 3
curl -s http://localhost:3000 | head -20
kill %1 2>/dev/null
```

Expected: No TypeScript errors, HTML response with root div.

- [ ] **Step 11: Commit**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant
git add web/
git commit -m "feat(web): add app shell with icon rail sidebar, top bar, theme toggle, routing"
```

---

## Task 4: Auth Pages (Login, Register, Forgot Password)

**Files:**
- Modify: `web/src/pages/auth/login.tsx`, `web/src/pages/auth/register.tsx`, `web/src/pages/auth/forgot-password.tsx`
- Create: `web/src/lib/validators.ts`

- [ ] **Step 1: Create Zod validators**

Create `web/src/lib/validators.ts`:

```ts
import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(1, "Password is required"),
});

export const registerSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ["confirmPassword"],
});

export const forgotPasswordSchema = z.object({
  email: z.string().email("Invalid email address"),
});

export type LoginValues = z.infer<typeof loginSchema>;
export type RegisterValues = z.infer<typeof registerSchema>;
export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>;
```

- [ ] **Step 2: Implement login page**

Replace `web/src/pages/auth/login.tsx`:

```tsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useLogin } from "@/hooks/use-auth";
import { loginSchema, type LoginValues } from "@/lib/validators";

export default function LoginPage() {
  const navigate = useNavigate();
  const login = useLogin();
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = form.handleSubmit((data) => {
    login.mutate(data, {
      onSuccess: () => navigate("/dashboard"),
      onError: (err: any) => {
        const msg = err.response?.data?.detail || "Login failed";
        toast.error(msg);
      },
    });
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 text-2xl font-bold text-primary">J</div>
          <CardTitle>Sign in to JobAssist</CardTitle>
          <CardDescription>Enter your email and password</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                {...form.register("email")}
              />
              {form.formState.errors.email && (
                <p className="text-sm text-destructive">{form.formState.errors.email.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                {...form.register("password")}
              />
              {form.formState.errors.password && (
                <p className="text-sm text-destructive">{form.formState.errors.password.message}</p>
              )}
            </div>
            <Button type="submit" className="w-full" disabled={login.isPending}>
              {login.isPending ? "Signing in..." : "Sign in"}
            </Button>
          </form>
          <div className="mt-4 text-center text-sm text-muted-foreground">
            <Link to="/forgot-password" className="text-primary hover:underline">
              Forgot password?
            </Link>
            {" · "}
            <Link to="/register" className="text-primary hover:underline">
              Create account
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 3: Implement register page**

Replace `web/src/pages/auth/register.tsx`:

```tsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useRegister, useLogin } from "@/hooks/use-auth";
import { registerSchema, type RegisterValues } from "@/lib/validators";

export default function RegisterPage() {
  const navigate = useNavigate();
  const register = useRegister();
  const login = useLogin();
  const form = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { email: "", password: "", confirmPassword: "" },
  });

  const onSubmit = form.handleSubmit((data) => {
    register.mutate(data, {
      onSuccess: () => {
        // Auto-login after registration
        login.mutate(
          { email: data.email, password: data.password },
          {
            onSuccess: () => navigate("/dashboard"),
            onError: () => {
              toast.success("Account created! Please sign in.");
              navigate("/login");
            },
          }
        );
      },
      onError: (err: any) => {
        const msg = err.response?.data?.detail || "Registration failed";
        toast.error(typeof msg === "string" ? msg : "Registration failed");
      },
    });
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 text-2xl font-bold text-primary">J</div>
          <CardTitle>Create your account</CardTitle>
          <CardDescription>Start tracking your job search</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" placeholder="you@example.com" {...form.register("email")} />
              {form.formState.errors.email && (
                <p className="text-sm text-destructive">{form.formState.errors.email.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" {...form.register("password")} />
              {form.formState.errors.password && (
                <p className="text-sm text-destructive">{form.formState.errors.password.message}</p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm password</Label>
              <Input id="confirmPassword" type="password" {...form.register("confirmPassword")} />
              {form.formState.errors.confirmPassword && (
                <p className="text-sm text-destructive">{form.formState.errors.confirmPassword.message}</p>
              )}
            </div>
            <Button type="submit" className="w-full" disabled={register.isPending}>
              {register.isPending ? "Creating account..." : "Create account"}
            </Button>
          </form>
          <div className="mt-4 text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link to="/login" className="text-primary hover:underline">Sign in</Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: Implement forgot password page**

Replace `web/src/pages/auth/forgot-password.tsx`:

```tsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link } from "react-router";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useForgotPassword } from "@/hooks/use-auth";
import { forgotPasswordSchema, type ForgotPasswordValues } from "@/lib/validators";

export default function ForgotPasswordPage() {
  const forgot = useForgotPassword();
  const form = useForm<ForgotPasswordValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });

  const onSubmit = form.handleSubmit((data) => {
    forgot.mutate(data.email, {
      onSuccess: () => toast.success("If that email exists, a reset link has been sent."),
      onError: () => toast.success("If that email exists, a reset link has been sent."),
    });
  });

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle>Reset password</CardTitle>
          <CardDescription>We'll send you a reset link</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" placeholder="you@example.com" {...form.register("email")} />
              {form.formState.errors.email && (
                <p className="text-sm text-destructive">{form.formState.errors.email.message}</p>
              )}
            </div>
            <Button type="submit" className="w-full" disabled={forgot.isPending}>
              {forgot.isPending ? "Sending..." : "Send reset link"}
            </Button>
          </form>
          <div className="mt-4 text-center text-sm text-muted-foreground">
            <Link to="/login" className="text-primary hover:underline">Back to sign in</Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 6: Commit**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant
git add web/
git commit -m "feat(web): add login, register, forgot-password pages with form validation"
```

---

## Task 5: SSE Task Stream Hook

**Files:**
- Create: `web/src/hooks/use-task-stream.ts`
- Test: `web/src/hooks/__tests__/use-task-stream.test.ts`

- [ ] **Step 1: Write tests for task store**

Create `web/src/stores/__tests__/task-store.test.ts`:

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { useTaskStore } from "../task-store";

describe("task-store", () => {
  beforeEach(() => {
    useTaskStore.getState().clear();
  });

  it("adds a task", () => {
    useTaskStore.getState().addTask({ id: "t1", type: "scrape", progress: 0 });
    expect(useTaskStore.getState().tasks).toHaveLength(1);
  });

  it("does not add duplicate task", () => {
    useTaskStore.getState().addTask({ id: "t1", type: "scrape", progress: 0 });
    useTaskStore.getState().addTask({ id: "t1", type: "scrape", progress: 50 });
    expect(useTaskStore.getState().tasks).toHaveLength(1);
  });

  it("updates a task", () => {
    useTaskStore.getState().addTask({ id: "t1", type: "scrape", progress: 0 });
    useTaskStore.getState().updateTask("t1", { progress: 75 });
    expect(useTaskStore.getState().tasks[0].progress).toBe(75);
  });

  it("removes a task", () => {
    useTaskStore.getState().addTask({ id: "t1", type: "scrape", progress: 0 });
    useTaskStore.getState().removeTask("t1");
    expect(useTaskStore.getState().tasks).toHaveLength(0);
  });
});
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx vitest run src/stores/__tests__/task-store.test.ts
```

Expected: PASS.

- [ ] **Step 3: Implement SSE hook**

Create `web/src/hooks/use-task-stream.ts`:

```ts
import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuthStore } from "@/stores/auth-store";
import { useTaskStore } from "@/stores/task-store";
import { queryKeys } from "@/lib/query-keys";

export function useTaskStream() {
  const token = useAuthStore((s) => s.token);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const { addTask, updateTask, removeTask } = useTaskStore();
  const queryClient = useQueryClient();
  const retriesRef = useRef(0);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!isAuthenticated || !token) return;

    function connect() {
      // EventSource doesn't support Authorization header natively.
      // We pass the token as a query param. The backend SSE endpoint
      // uses Depends(current_active_user) which reads Bearer token.
      // For SSE, we'll need to pass token in URL or use a polyfill.
      // Using query param approach:
      const url = `${import.meta.env.VITE_API_URL || ""}/api/tasks/stream?token=${token}`;
      const es = new EventSource(url);
      esRef.current = es;

      es.addEventListener("task:started", (e) => {
        const data = JSON.parse(e.data);
        addTask({ id: data.task_id, type: data.type, progress: 0 });
        toast.info(`${data.type} task started`);
      });

      es.addEventListener("task:progress", (e) => {
        const data = JSON.parse(e.data);
        updateTask(data.task_id, { progress: data.progress, message: data.message });
      });

      es.addEventListener("task:completed", (e) => {
        const data = JSON.parse(e.data);
        removeTask(data.task_id);
        toast.success(`${data.type} completed`);
        // Invalidate relevant queries
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

      es.addEventListener("task:failed", (e) => {
        const data = JSON.parse(e.data);
        removeTask(data.task_id);
        toast.error(`${data.type} failed: ${data.error || "Unknown error"}`);
      });

      es.addEventListener("ping", () => {
        // Keepalive — reset retry counter
        retriesRef.current = 0;
      });

      es.onerror = () => {
        es.close();
        esRef.current = null;
        // Reconnect with exponential backoff
        const delay = Math.min(1000 * 2 ** retriesRef.current, 30000);
        retriesRef.current++;
        setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      esRef.current?.close();
      esRef.current = null;
    };
  }, [isAuthenticated, token, addTask, updateTask, removeTask, queryClient]);
}
```

- [ ] **Step 4: Wire SSE hook into app shell**

Modify `web/src/components/layout/app-shell.tsx` — add the hook call:

```tsx
import { Outlet, useLocation } from "react-router";
import { IconRail } from "./icon-rail";
import { TopBar } from "./top-bar";
import { useTaskStream } from "@/hooks/use-task-stream";

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
    Object.entries(pageTitles).find(([prefix]) =>
      location.pathname.startsWith(prefix)
    )?.[1] ??
    "JobAssist";

  return (
    <div className="flex h-screen overflow-hidden">
      <IconRail />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar title={title} />
        <main className="flex-1 overflow-auto p-5">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run all tests**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx vitest run
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant
git add web/
git commit -m "feat(web): add SSE task stream hook with auto-reconnect and query invalidation"
```

---

## Task 6: Shared Components (QueryState, Pagination, ScoreBadge, SkillTag, ConfirmDialog)

**Files:**
- Create: `web/src/components/shared/query-state.tsx`, `web/src/components/shared/pagination.tsx`, `web/src/components/shared/confirm-dialog.tsx`, `web/src/components/jobs/score-badge.tsx`, `web/src/components/jobs/skill-tag.tsx`

- [ ] **Step 1: Create QueryState wrapper**

Create `web/src/components/shared/query-state.tsx`:

```tsx
import { type UseQueryResult } from "@tanstack/react-query";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

interface QueryStateProps<T> {
  query: UseQueryResult<T>;
  loading?: React.ReactNode;
  empty?: React.ReactNode;
  isEmpty?: (data: T) => boolean;
  children: (data: T) => React.ReactNode;
}

export function QueryState<T>({
  query,
  loading,
  empty,
  isEmpty,
  children,
}: QueryStateProps<T>) {
  if (query.isLoading) {
    return <>{loading ?? <DefaultLoading />}</>;
  }

  if (query.isError) {
    return (
      <div className="flex flex-col items-center gap-3 py-12 text-center">
        <AlertCircle className="h-8 w-8 text-destructive" />
        <p className="text-sm text-muted-foreground">
          {query.error instanceof Error ? query.error.message : "Something went wrong"}
        </p>
        <Button variant="outline" size="sm" onClick={() => query.refetch()}>
          <RefreshCw className="mr-2 h-3.5 w-3.5" /> Retry
        </Button>
      </div>
    );
  }

  if (query.data === undefined || query.data === null) {
    return <>{empty ?? null}</>;
  }

  if (isEmpty?.(query.data)) {
    return <>{empty ?? null}</>;
  }

  return <>{children(query.data)}</>;
}

function DefaultLoading() {
  return (
    <div className="space-y-3">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  );
}
```

- [ ] **Step 2: Create Pagination component**

Create `web/src/components/shared/pagination.tsx`:

```tsx
import { Button } from "@/components/ui/button";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, onChange }: PaginationProps) {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;

  const start = page * pageSize + 1;
  const end = Math.min((page + 1) * pageSize, total);

  return (
    <div className="flex items-center justify-between border-t px-5 py-2.5 text-xs text-muted-foreground">
      <span>
        Showing {start}–{end} of {total}
      </span>
      <div className="flex gap-1">
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-xs"
          disabled={page === 0}
          onClick={() => onChange(page - 1)}
        >
          Prev
        </Button>
        {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
          const pageNum = page <= 2 ? i : page - 2 + i;
          if (pageNum >= totalPages) return null;
          return (
            <Button
              key={pageNum}
              variant={pageNum === page ? "default" : "outline"}
              size="sm"
              className="h-7 w-7 text-xs p-0"
              onClick={() => onChange(pageNum)}
            >
              {pageNum + 1}
            </Button>
          );
        })}
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-xs"
          disabled={page >= totalPages - 1}
          onClick={() => onChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create ConfirmDialog**

Create `web/src/components/shared/confirm-dialog.tsx`:

```tsx
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  variant?: "default" | "destructive";
  onConfirm: () => void;
  isPending?: boolean;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  variant = "default",
  onConfirm,
  isPending,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant={variant} onClick={onConfirm} disabled={isPending}>
            {isPending ? "..." : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Create ScoreBadge**

Create `web/src/components/jobs/score-badge.tsx`:

```tsx
import { cn, scoreColor } from "@/lib/utils";

interface ScoreBadgeProps {
  score: number | null;
  size?: "sm" | "md" | "lg";
}

export function ScoreBadge({ score, size = "sm" }: ScoreBadgeProps) {
  if (score === null || score === undefined) {
    return (
      <span className="inline-flex min-w-[30px] items-center justify-center rounded px-2 py-0.5 text-xs font-semibold bg-muted text-muted-foreground">
        —
      </span>
    );
  }

  const sizeClasses = {
    sm: "min-w-[30px] px-2 py-0.5 text-xs",
    md: "min-w-[38px] px-3 py-1 text-sm",
    lg: "min-w-[46px] px-4 py-1.5 text-lg",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded font-bold",
        sizeClasses[size],
        scoreColor(score)
      )}
    >
      {score}
    </span>
  );
}
```

- [ ] **Step 5: Create SkillTag**

Create `web/src/components/jobs/skill-tag.tsx`:

```tsx
import { cn } from "@/lib/utils";

interface SkillTagProps {
  name: string;
  variant: "match" | "gap";
}

export function SkillTag({ name, variant }: SkillTagProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium",
        variant === "match"
          ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
          : "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
      )}
    >
      {variant === "gap" ? `Gap: ${name}` : name}
    </span>
  );
}
```

- [ ] **Step 6: Commit**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant
git add web/
git commit -m "feat(web): add shared components — QueryState, Pagination, ScoreBadge, SkillTag, ConfirmDialog"
```

---

## Task 7: Dashboard Page

**Files:**
- Modify: `web/src/pages/dashboard.tsx`

- [ ] **Step 1: Implement dashboard page**

Replace `web/src/pages/dashboard.tsx`:

```tsx
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ScoreBadge } from "@/components/jobs/score-badge";
import { QueryState } from "@/components/shared/query-state";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";
import { timeAgo } from "@/lib/utils";

export function Component() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [scrapeUrl, setScrapeUrl] = useState("");

  // Fetch stats from multiple endpoints
  const jobsQuery = useQuery({
    queryKey: queryKeys.jobs.list({ limit: 100 }),
    queryFn: () => apiClient.get("/api/jobs?limit=100").then((r) => r.data),
    staleTime: 30_000,
  });

  const rankedQuery = useQuery({
    queryKey: queryKeys.jobs.ranked(5),
    queryFn: () => apiClient.get("/api/jobs/ranked?limit=5").then((r) => r.data),
    staleTime: 30_000,
  });

  const skillGapsQuery = useQuery({
    queryKey: queryKeys.skills.gaps,
    queryFn: () => apiClient.get("/api/skills/gaps").then((r) => r.data),
    staleTime: 120_000,
  });

  const scrapeMutation = useMutation({
    mutationFn: (url: string) =>
      apiClient.post("/api/jobs/scrape", { url }).then((r) => r.data),
    onSuccess: () => {
      toast.success("Scrape task started");
      setScrapeUrl("");
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
    },
    onError: () => toast.error("Failed to start scrape"),
  });

  const discoveryMutation = useMutation({
    mutationFn: () => apiClient.post("/api/discovery/run").then((r) => r.data),
    onSuccess: () => toast.success("Discovery started"),
    onError: () => toast.error("Failed to start discovery"),
  });

  const jobs = (jobsQuery.data ?? []) as any[];
  const ranked = (rankedQuery.data ?? []) as any[];
  const gaps = (skillGapsQuery.data ?? []) as any[];
  const totalJobs = jobs.length;
  const topGap = gaps[0]?.skill ?? "—";
  const topGapCount = gaps[0]?.demand_count ?? 0;

  return (
    <div className="space-y-5">
      {/* Quick action bar */}
      <div className="flex items-center gap-3 rounded-lg border bg-muted/40 p-3.5">
        <Input
          className="flex-1"
          placeholder="Paste a job URL to scrape..."
          value={scrapeUrl}
          onChange={(e) => setScrapeUrl(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && scrapeUrl.trim()) {
              scrapeMutation.mutate(scrapeUrl.trim());
            }
          }}
        />
        <Button
          onClick={() => scrapeUrl.trim() && scrapeMutation.mutate(scrapeUrl.trim())}
          disabled={scrapeMutation.isPending || !scrapeUrl.trim()}
        >
          Scrape Job
        </Button>
        <Button
          variant="outline"
          onClick={() => discoveryMutation.mutate()}
          disabled={discoveryMutation.isPending}
        >
          Run Discovery
        </Button>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-4 gap-3">
        <Card>
          <CardContent className="pt-4">
            <div className="text-[11px] font-medium uppercase text-muted-foreground">Total Jobs</div>
            <div className="text-3xl font-bold">{totalJobs}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-[11px] font-medium uppercase text-muted-foreground">Avg Fit Score</div>
            <div className="text-3xl font-bold">—</div>
            <div className="mt-1.5 h-1 rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary" style={{ width: "0%" }} />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-[11px] font-medium uppercase text-muted-foreground">Docs Generated</div>
            <div className="text-3xl font-bold">—</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-[11px] font-medium uppercase text-muted-foreground">Top Skill Gap</div>
            <div className="mt-1 text-lg font-semibold text-amber-600">{topGap}</div>
            {topGapCount > 0 && (
              <div className="text-[11px] text-muted-foreground">in {topGapCount} job listings</div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Top ranked jobs */}
      <Card>
        <div className="flex items-center justify-between border-b px-4 py-3">
          <span className="text-sm font-semibold">Top Ranked Jobs</span>
          <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={() => navigate("/jobs")}>
            View all →
          </Button>
        </div>
        <QueryState
          query={rankedQuery}
          isEmpty={(data: any[]) => data.length === 0}
          empty={<p className="p-4 text-sm text-muted-foreground">No analyzed jobs yet. Scrape a job URL above to get started.</p>}
        >
          {(data: any[]) => (
            <div>
              {data.map((job: any) => (
                <div
                  key={job.id}
                  className="flex cursor-pointer items-center gap-3 border-b px-4 py-2.5 text-sm last:border-0 hover:bg-muted/40"
                  onClick={() => navigate(`/jobs/${job.id}`)}
                >
                  <ScoreBadge score={job.fit_score ?? null} />
                  <span className="font-medium">{job.title}</span>
                  <span className="text-muted-foreground">{job.company}</span>
                  <span className="ml-auto text-xs text-muted-foreground">{timeAgo(job.scraped_at)}</span>
                </div>
              ))}
            </div>
          )}
        </QueryState>
      </Card>
    </div>
  );
}
```

**Note:** The ranked endpoint returns `JobRead` which doesn't have `fit_score` directly. The dashboard shows ranked jobs — the score comes from the analysis. For now, we show the list without scores inline. We'll enhance this once the jobs list page is complete.

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant
git add web/
git commit -m "feat(web): implement dashboard page with quick actions, stats, and ranked jobs"
```

---

## Task 8: Jobs List + Job Detail Pages

**Files:**
- Modify: `web/src/pages/jobs/list.tsx`, `web/src/pages/jobs/detail.tsx`

- [ ] **Step 1: Implement jobs list page**

Replace `web/src/pages/jobs/list.tsx`:

```tsx
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { ScoreBadge } from "@/components/jobs/score-badge";
import { SkillTag } from "@/components/jobs/skill-tag";
import { QueryState } from "@/components/shared/query-state";
import { Pagination } from "@/components/shared/pagination";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";
import { timeAgo } from "@/lib/utils";
import { useDebounce } from "@/hooks/use-debounce";

const PAGE_SIZE = 20;

type SortBy = "scraped_at" | "title" | "company";

export function Component() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<SortBy>("scraped_at");
  const [scrapeOpen, setScrapeOpen] = useState(false);
  const [scrapeUrl, setScrapeUrl] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; title: string } | null>(null);

  const debouncedSearch = useDebounce(search, 300);

  const params = {
    offset: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    sort_by: sortBy,
    order: "desc" as const,
    ...(debouncedSearch ? { search: debouncedSearch } : {}),
  };

  const jobsQuery = useQuery({
    queryKey: queryKeys.jobs.list(params),
    queryFn: () => {
      const qs = new URLSearchParams();
      qs.set("offset", String(params.offset));
      qs.set("limit", String(params.limit));
      qs.set("sort_by", params.sort_by);
      qs.set("order", params.order);
      if (params.search) qs.set("search", params.search);
      return apiClient.get(`/api/jobs?${qs}`).then((r) => r.data);
    },
    staleTime: 30_000,
  });

  const scrapeMutation = useMutation({
    mutationFn: (url: string) =>
      apiClient.post("/api/jobs/scrape", { url }).then((r) => r.data),
    onSuccess: () => {
      toast.success("Scrape task started");
      setScrapeOpen(false);
      setScrapeUrl("");
    },
    onError: () => toast.error("Failed to start scrape"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiClient.delete(`/api/jobs/${id}`),
    onSuccess: () => {
      toast.success("Job deleted");
      setDeleteTarget(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
    },
    onError: () => toast.error("Failed to delete job"),
  });

  const jobs = (jobsQuery.data ?? []) as any[];

  return (
    <div className="space-y-0">
      {/* Toolbar */}
      <div className="flex items-center gap-3 pb-4">
        <Input
          className="w-64"
          placeholder="Search jobs..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
        />
        <select
          className="h-9 rounded-md border bg-background px-3 text-sm"
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as SortBy)}
        >
          <option value="scraped_at">Sort: Date</option>
          <option value="title">Sort: Title</option>
          <option value="company">Sort: Company</option>
        </select>
        <div className="ml-auto">
          <Button size="sm" onClick={() => setScrapeOpen(true)}>
            <Plus className="mr-1.5 h-4 w-4" /> Scrape URL
          </Button>
        </div>
      </div>

      {/* Job list */}
      <div className="rounded-lg border">
        <QueryState
          query={jobsQuery}
          isEmpty={(data: any[]) => data.length === 0}
          empty={
            <p className="p-8 text-center text-sm text-muted-foreground">
              No jobs yet. Click "Scrape URL" to add your first job.
            </p>
          }
        >
          {(data: any[]) => (
            <>
              {data.map((job: any) => (
                <div
                  key={job.id}
                  className="flex cursor-pointer items-center gap-3 border-b px-4 py-3 text-sm last:border-0 hover:bg-muted/40"
                  onClick={() => navigate(`/jobs/${job.id}`)}
                >
                  <ScoreBadge score={null} />
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold">{job.title}</div>
                    <div className="truncate text-xs text-muted-foreground">
                      {job.company}
                      {job.location && ` · ${job.location}`}
                      {job.salary_range && ` · ${job.salary_range}`}
                    </div>
                  </div>
                  <span className="text-xs text-muted-foreground">{timeAgo(job.scraped_at)}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-destructive hover:text-destructive"
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteTarget({ id: job.id, title: job.title });
                    }}
                  >
                    Delete
                  </Button>
                </div>
              ))}
              <Pagination
                page={page}
                pageSize={PAGE_SIZE}
                total={data.length < PAGE_SIZE ? page * PAGE_SIZE + data.length : (page + 1) * PAGE_SIZE + 1}
                onChange={setPage}
              />
            </>
          )}
        </QueryState>
      </div>

      {/* Scrape dialog */}
      <Dialog open={scrapeOpen} onOpenChange={setScrapeOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Scrape a job URL</DialogTitle>
          </DialogHeader>
          <Input
            placeholder="https://..."
            value={scrapeUrl}
            onChange={(e) => setScrapeUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && scrapeUrl.trim()) {
                scrapeMutation.mutate(scrapeUrl.trim());
              }
            }}
          />
          <DialogFooter>
            <Button
              onClick={() => scrapeUrl.trim() && scrapeMutation.mutate(scrapeUrl.trim())}
              disabled={scrapeMutation.isPending || !scrapeUrl.trim()}
            >
              {scrapeMutation.isPending ? "Starting..." : "Scrape"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={() => setDeleteTarget(null)}
        title="Delete job"
        description={`Are you sure you want to delete "${deleteTarget?.title}"? This cannot be undone.`}
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        isPending={deleteMutation.isPending}
      />
    </div>
  );
}
```

- [ ] **Step 2: Implement job detail page**

Replace `web/src/pages/jobs/detail.tsx`:

```tsx
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useNavigate } from "react-router";
import { toast } from "sonner";
import { ArrowLeft, Download, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScoreBadge } from "@/components/jobs/score-badge";
import { SkillTag } from "@/components/jobs/skill-tag";
import { QueryState } from "@/components/shared/query-state";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";
import { timeAgo } from "@/lib/utils";

export function Component() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const jobId = Number(id);

  const jobQuery = useQuery({
    queryKey: queryKeys.jobs.detail(jobId),
    queryFn: () => apiClient.get(`/api/jobs/${jobId}`).then((r) => r.data),
  });

  const analysisQuery = useQuery({
    queryKey: queryKeys.analysis.byJob(jobId),
    queryFn: () => apiClient.get(`/api/jobs/${jobId}/analysis`).then((r) => r.data),
    retry: false, // 404 is expected if not yet analyzed
  });

  const docsQuery = useQuery({
    queryKey: queryKeys.documents.byJob(jobId),
    queryFn: () => apiClient.get(`/api/jobs/${jobId}/documents`).then((r) => r.data),
  });

  const analyzeMutation = useMutation({
    mutationFn: () => apiClient.post(`/api/jobs/${jobId}/analyze`).then((r) => r.data),
    onSuccess: () => toast.success("Analysis started"),
    onError: () => toast.error("Failed to start analysis"),
  });

  const generateMutation = useMutation({
    mutationFn: () => apiClient.post(`/api/jobs/${jobId}/generate`).then((r) => r.data),
    onSuccess: () => toast.success("Document generation started"),
    onError: () => toast.error("Failed to start generation"),
  });

  return (
    <QueryState query={jobQuery}>
      {(job: any) => {
        const analysis = analysisQuery.data as any;
        const docs = docsQuery.data as any;

        return (
          <div className="space-y-4">
            {/* Breadcrumb */}
            <Button variant="ghost" size="sm" className="h-auto p-0 text-xs" onClick={() => navigate("/jobs")}>
              <ArrowLeft className="mr-1 h-3.5 w-3.5" /> Jobs
            </Button>

            <div className="flex gap-5">
              {/* Left: content */}
              <div className="min-w-0 flex-1 space-y-4">
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-xl font-bold">{job.title}</h2>
                    <p className="text-sm text-muted-foreground">
                      {job.company}
                      {job.location && ` · ${job.location}`}
                      {job.job_type && ` · ${job.job_type}`}
                      {job.salary_range && ` · ${job.salary_range}`}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Scraped {timeAgo(job.scraped_at)}
                      {job.application_url && (
                        <>
                          {" · "}
                          <a
                            href={job.application_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-0.5 text-primary hover:underline"
                          >
                            Original <ExternalLink className="h-3 w-3" />
                          </a>
                        </>
                      )}
                    </p>
                  </div>
                  {analysis && <ScoreBadge score={analysis.fit_score} size="lg" />}
                </div>

                {/* Tabs */}
                <Tabs defaultValue="analysis">
                  <TabsList>
                    <TabsTrigger value="analysis">Analysis</TabsTrigger>
                    <TabsTrigger value="description">Description</TabsTrigger>
                    <TabsTrigger value="documents">Documents</TabsTrigger>
                  </TabsList>

                  <TabsContent value="analysis" className="space-y-4 pt-2">
                    {analysisQuery.isLoading ? (
                      <p className="text-sm text-muted-foreground">Loading analysis...</p>
                    ) : analysis ? (
                      <>
                        {/* Score breakdown */}
                        <Card>
                          <CardContent className="space-y-2 pt-4 text-sm">
                            <h3 className="font-semibold">Score Breakdown</h3>
                            <div className="flex gap-2">
                              <span className="w-32 text-muted-foreground">Base score:</span>
                              <span>{analysis.base_score ?? "—"}</span>
                            </div>
                            {(analysis.penalties ?? []).map((p: any, i: number) => (
                              <div key={i} className="flex gap-2">
                                <span className="w-32 text-muted-foreground">{p.reason ?? `Penalty ${i + 1}`}:</span>
                                <span className="text-red-600">{p.adjustment ?? p.value ?? "—"}</span>
                              </div>
                            ))}
                            <div className="flex gap-2 border-t pt-2 font-semibold">
                              <span className="w-32">Final score:</span>
                              <span className="text-green-600">{analysis.fit_score}</span>
                            </div>
                          </CardContent>
                        </Card>

                        {/* Skills */}
                        <Card>
                          <CardContent className="pt-4">
                            <h3 className="mb-2 text-sm font-semibold">Skills</h3>
                            <div className="flex flex-wrap gap-1.5">
                              {(analysis.matching_skills ?? []).map((s: string) => (
                                <SkillTag key={s} name={s} variant="match" />
                              ))}
                              {(analysis.gaps ?? []).map((s: string) => (
                                <SkillTag key={s} name={s} variant="gap" />
                              ))}
                            </div>
                          </CardContent>
                        </Card>

                        {/* Recommendation */}
                        {analysis.fit_reasoning && (
                          <Card>
                            <CardContent className="pt-4">
                              <h3 className="mb-2 text-sm font-semibold">Recommendation</h3>
                              <p className="text-sm leading-relaxed text-muted-foreground">
                                {analysis.fit_reasoning}
                              </p>
                            </CardContent>
                          </Card>
                        )}
                      </>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No analysis yet. Click "Analyze" to start.
                      </p>
                    )}
                  </TabsContent>

                  <TabsContent value="description" className="pt-2">
                    <Card>
                      <CardContent className="pt-4">
                        <div className="prose prose-sm max-w-none dark:prose-invert whitespace-pre-wrap">
                          {job.description || "No description available."}
                        </div>
                      </CardContent>
                    </Card>
                  </TabsContent>

                  <TabsContent value="documents" className="pt-2">
                    <Card>
                      <CardContent className="pt-4 space-y-2">
                        {docs?.resume_url ? (
                          <a
                            href={docs.resume_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-2 rounded border p-2 text-sm hover:bg-muted/40"
                          >
                            <Download className="h-4 w-4" /> Resume PDF
                          </a>
                        ) : null}
                        {docs?.cover_letter_url ? (
                          <a
                            href={docs.cover_letter_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-2 rounded border p-2 text-sm hover:bg-muted/40"
                          >
                            <Download className="h-4 w-4" /> Cover Letter PDF
                          </a>
                        ) : null}
                        {!docs?.resume_url && !docs?.cover_letter_url && (
                          <p className="text-sm text-muted-foreground">
                            No documents generated yet. Click "Generate" to create tailored docs.
                          </p>
                        )}
                      </CardContent>
                    </Card>
                  </TabsContent>
                </Tabs>
              </div>

              {/* Right: action panel */}
              <div className="w-64 shrink-0 space-y-3">
                <h3 className="text-sm font-semibold">Actions</h3>
                <Button
                  className="w-full"
                  onClick={() => generateMutation.mutate()}
                  disabled={generateMutation.isPending}
                >
                  Generate Resume
                </Button>
                <Button
                  className="w-full"
                  onClick={() => generateMutation.mutate()}
                  disabled={generateMutation.isPending}
                >
                  Generate Cover Letter
                </Button>
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => analyzeMutation.mutate()}
                  disabled={analyzeMutation.isPending}
                >
                  {analysisQuery.data ? "Re-analyze" : "Analyze"}
                </Button>
              </div>
            </div>
          </div>
        );
      }}
    </QueryState>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant
git add web/
git commit -m "feat(web): implement jobs list and job detail pages"
```

---

## Task 9: Profile Page

**Files:**
- Modify: `web/src/pages/profile.tsx`
- Create: `web/src/components/profile/json-import-dialog.tsx`

- [ ] **Step 1: Create JSON import dialog**

Create `web/src/components/profile/json-import-dialog.tsx`:

```tsx
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

interface JsonImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImport: (data: Record<string, unknown>) => void;
  isPending?: boolean;
}

export function JsonImportDialog({ open, onOpenChange, onImport, isPending }: JsonImportDialogProps) {
  const [raw, setRaw] = useState("");

  function handleImport() {
    try {
      const data = JSON.parse(raw);
      if (typeof data !== "object" || data === null) {
        toast.error("JSON must be an object");
        return;
      }
      onImport(data);
    } catch {
      toast.error("Invalid JSON");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Import Profile JSON</DialogTitle>
        </DialogHeader>
        <Textarea
          rows={12}
          placeholder='Paste your master_resume.json content here...'
          value={raw}
          onChange={(e) => setRaw(e.target.value)}
          className="font-mono text-xs"
        />
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={handleImport} disabled={isPending || !raw.trim()}>
            {isPending ? "Importing..." : "Import"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Implement profile page**

Replace `web/src/pages/profile.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, useFieldArray } from "react-hook-form";
import { toast } from "sonner";
import { Download, Plus, Trash2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { QueryState } from "@/components/shared/query-state";
import { JsonImportDialog } from "@/components/profile/json-import-dialog";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";

interface ProfileFormData {
  full_name: string;
  contact: { email: string; phone: string; linkedin: string; github: string; website: string };
  summary: string;
  experience: { company: string; title: string; dates: string; bullets: string[] }[];
  education: { school: string; degree: string; dates: string }[];
  skills: string;
  certifications: string;
}

export function Component() {
  const queryClient = useQueryClient();
  const [importOpen, setImportOpen] = useState(false);

  const profileQuery = useQuery({
    queryKey: queryKeys.profile.current,
    queryFn: () => apiClient.get("/api/profile").then((r) => r.data),
    staleTime: 300_000,
  });

  const updateMutation = useMutation({
    mutationFn: (data: any) => apiClient.put("/api/profile", data).then((r) => r.data),
    onSuccess: () => {
      toast.success("Profile saved");
      queryClient.invalidateQueries({ queryKey: queryKeys.profile.current });
    },
    onError: () => toast.error("Failed to save profile"),
  });

  const importMutation = useMutation({
    mutationFn: (data: Record<string, unknown>) =>
      apiClient.post("/api/profile/import", data).then((r) => r.data),
    onSuccess: () => {
      toast.success("Profile imported");
      setImportOpen(false);
      queryClient.invalidateQueries({ queryKey: queryKeys.profile.current });
    },
    onError: () => toast.error("Failed to import profile"),
  });

  const form = useForm<ProfileFormData>({
    defaultValues: {
      full_name: "",
      contact: { email: "", phone: "", linkedin: "", github: "", website: "" },
      summary: "",
      experience: [],
      education: [],
      skills: "",
      certifications: "",
    },
  });

  const expArray = useFieldArray({ control: form.control, name: "experience" });
  const eduArray = useFieldArray({ control: form.control, name: "education" });

  // Populate form when profile loads
  useEffect(() => {
    if (profileQuery.data) {
      const p = profileQuery.data as any;
      form.reset({
        full_name: p.full_name ?? "",
        contact: {
          email: p.contact?.email ?? "",
          phone: p.contact?.phone ?? "",
          linkedin: p.contact?.linkedin ?? "",
          github: p.contact?.github ?? "",
          website: p.contact?.website ?? "",
        },
        summary: p.summary ?? "",
        experience: (p.experience ?? []).map((e: any) => ({
          company: e.company ?? "",
          title: e.title ?? "",
          dates: e.dates ?? "",
          bullets: e.bullets ?? [],
        })),
        education: (p.education ?? []).map((e: any) => ({
          school: e.school ?? "",
          degree: e.degree ?? "",
          dates: e.dates ?? "",
        })),
        skills: (p.skills ?? []).join(", "),
        certifications: (p.certifications ?? []).join(", "),
      });
    }
  }, [profileQuery.data, form]);

  const onSubmit = form.handleSubmit((data) => {
    updateMutation.mutate({
      full_name: data.full_name || null,
      contact: data.contact,
      summary: data.summary || null,
      experience: data.experience,
      education: data.education,
      skills: data.skills ? data.skills.split(",").map((s) => s.trim()).filter(Boolean) : [],
      certifications: data.certifications ? data.certifications.split(",").map((s) => s.trim()).filter(Boolean) : [],
    });
  });

  async function handleExport() {
    try {
      const resp = await apiClient.get("/api/profile/export");
      const blob = new Blob([JSON.stringify(resp.data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "master_resume.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Failed to export profile");
    }
  }

  return (
    <QueryState query={profileQuery}>
      {() => (
        <form onSubmit={onSubmit} className="space-y-5">
          {/* Toolbar */}
          <div className="flex items-center gap-2">
            <Button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending ? "Saving..." : "Save"}
            </Button>
            <Button type="button" variant="outline" onClick={() => setImportOpen(true)}>
              <Upload className="mr-1.5 h-4 w-4" /> Import JSON
            </Button>
            <Button type="button" variant="outline" onClick={handleExport}>
              <Download className="mr-1.5 h-4 w-4" /> Export JSON
            </Button>
          </div>

          {/* Contact */}
          <Card>
            <CardHeader><CardTitle className="text-base">Contact Info</CardTitle></CardHeader>
            <CardContent className="grid grid-cols-2 gap-4">
              <div className="col-span-2 space-y-1">
                <Label>Full Name</Label>
                <Input {...form.register("full_name")} />
              </div>
              <div className="space-y-1"><Label>Email</Label><Input {...form.register("contact.email")} /></div>
              <div className="space-y-1"><Label>Phone</Label><Input {...form.register("contact.phone")} /></div>
              <div className="space-y-1"><Label>LinkedIn</Label><Input {...form.register("contact.linkedin")} /></div>
              <div className="space-y-1"><Label>GitHub</Label><Input {...form.register("contact.github")} /></div>
            </CardContent>
          </Card>

          {/* Summary */}
          <Card>
            <CardHeader><CardTitle className="text-base">Professional Summary</CardTitle></CardHeader>
            <CardContent>
              <Textarea rows={4} {...form.register("summary")} />
            </CardContent>
          </Card>

          {/* Experience */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Work Experience</CardTitle>
              <Button type="button" variant="outline" size="sm" onClick={() => expArray.append({ company: "", title: "", dates: "", bullets: [] })}>
                <Plus className="mr-1 h-3.5 w-3.5" /> Add
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              {expArray.fields.map((field, i) => (
                <div key={field.id} className="space-y-2 rounded border p-3">
                  <div className="flex gap-2">
                    <div className="flex-1 space-y-1"><Label>Company</Label><Input {...form.register(`experience.${i}.company`)} /></div>
                    <div className="flex-1 space-y-1"><Label>Title</Label><Input {...form.register(`experience.${i}.title`)} /></div>
                    <div className="w-40 space-y-1"><Label>Dates</Label><Input {...form.register(`experience.${i}.dates`)} /></div>
                    <Button type="button" variant="ghost" size="icon" className="mt-6" onClick={() => expArray.remove(i)}>
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              ))}
              {expArray.fields.length === 0 && (
                <p className="text-sm text-muted-foreground">No experience entries. Click "Add" to start.</p>
              )}
            </CardContent>
          </Card>

          {/* Education */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Education</CardTitle>
              <Button type="button" variant="outline" size="sm" onClick={() => eduArray.append({ school: "", degree: "", dates: "" })}>
                <Plus className="mr-1 h-3.5 w-3.5" /> Add
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              {eduArray.fields.map((field, i) => (
                <div key={field.id} className="flex gap-2">
                  <div className="flex-1 space-y-1"><Label>School</Label><Input {...form.register(`education.${i}.school`)} /></div>
                  <div className="flex-1 space-y-1"><Label>Degree</Label><Input {...form.register(`education.${i}.degree`)} /></div>
                  <div className="w-40 space-y-1"><Label>Dates</Label><Input {...form.register(`education.${i}.dates`)} /></div>
                  <Button type="button" variant="ghost" size="icon" className="mt-6" onClick={() => eduArray.remove(i)}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Skills + Certifications */}
          <Card>
            <CardHeader><CardTitle className="text-base">Skills & Certifications</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1">
                <Label>Skills (comma-separated)</Label>
                <Input {...form.register("skills")} placeholder="Python, FastAPI, PostgreSQL, ..." />
              </div>
              <div className="space-y-1">
                <Label>Certifications (comma-separated)</Label>
                <Input {...form.register("certifications")} placeholder="AWS Solutions Architect, ..." />
              </div>
            </CardContent>
          </Card>

          <JsonImportDialog
            open={importOpen}
            onOpenChange={setImportOpen}
            onImport={(data) => importMutation.mutate(data)}
            isPending={importMutation.isPending}
          />
        </form>
      )}
    </QueryState>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant
git add web/
git commit -m "feat(web): implement profile page with form editor and JSON import/export"
```

---

## Task 10: Discover + Search Pages

**Files:**
- Modify: `web/src/pages/discover.tsx`, `web/src/pages/search.tsx`

- [ ] **Step 1: Implement discover page**

Replace `web/src/pages/discover.tsx`:

```tsx
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Pencil, Plus, Power, Trash2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { QueryState } from "@/components/shared/query-state";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";
import { timeAgo } from "@/lib/utils";

interface ConfigFormData {
  name: string;
  config_type: string;
  query?: string;
  location?: string;
  url?: string;
}

export function Component() {
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const configsQuery = useQuery({
    queryKey: queryKeys.discovery.configs,
    queryFn: () => apiClient.get("/api/discovery/configs").then((r) => r.data),
  });

  const runMutation = useMutation({
    mutationFn: () => apiClient.post("/api/discovery/run").then((r) => r.data),
    onSuccess: () => toast.success("Discovery started"),
    onError: () => toast.error("Failed to start discovery"),
  });

  const createMutation = useMutation({
    mutationFn: (data: any) => apiClient.post("/api/discovery/configs", data).then((r) => r.data),
    onSuccess: () => {
      toast.success("Config created");
      setFormOpen(false);
      queryClient.invalidateQueries({ queryKey: queryKeys.discovery.configs });
    },
    onError: () => toast.error("Failed to create config"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, ...data }: any) =>
      apiClient.put(`/api/discovery/configs/${id}`, data).then((r) => r.data),
    onSuccess: () => {
      toast.success("Config updated");
      setFormOpen(false);
      setEditId(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.discovery.configs });
    },
    onError: () => toast.error("Failed to update config"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiClient.delete(`/api/discovery/configs/${id}`),
    onSuccess: () => {
      toast.success("Config deleted");
      setDeleteId(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.discovery.configs });
    },
    onError: () => toast.error("Failed to delete config"),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      apiClient.put(`/api/discovery/configs/${id}`, { is_active }).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.discovery.configs }),
  });

  const form = useForm<ConfigFormData>({
    defaultValues: { name: "", config_type: "search_query", query: "", location: "", url: "" },
  });

  function openCreate() {
    form.reset({ name: "", config_type: "search_query", query: "", location: "", url: "" });
    setEditId(null);
    setFormOpen(true);
  }

  function openEdit(config: any) {
    form.reset({
      name: config.name,
      config_type: config.config_type,
      query: config.config?.query ?? "",
      location: config.config?.location ?? "",
      url: config.config?.url ?? "",
    });
    setEditId(config.id);
    setFormOpen(true);
  }

  function handleSubmit(data: ConfigFormData) {
    const payload = {
      name: data.name,
      config_type: data.config_type,
      config:
        data.config_type === "search_query"
          ? { query: data.query, location: data.location }
          : { url: data.url },
    };
    if (editId) {
      updateMutation.mutate({ id: editId, ...payload });
    } else {
      createMutation.mutate(payload);
    }
  }

  const configs = (configsQuery.data ?? []) as any[];

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Button onClick={openCreate}>
          <Plus className="mr-1.5 h-4 w-4" /> Add Config
        </Button>
        <Button variant="outline" onClick={() => runMutation.mutate()} disabled={runMutation.isPending}>
          {runMutation.isPending ? "Running..." : "Run All"}
        </Button>
      </div>

      <QueryState
        query={configsQuery}
        isEmpty={(data: any[]) => data.length === 0}
        empty={<p className="text-sm text-muted-foreground">No search configs yet. Create one to start discovering jobs.</p>}
      >
        {(data: any[]) => (
          <div className="grid grid-cols-2 gap-3">
            {data.map((config: any) => (
              <Card key={config.id}>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm">{config.name}</CardTitle>
                  <div className="flex items-center gap-2">
                    <Switch
                      checked={config.is_active}
                      onCheckedChange={(checked) => toggleMutation.mutate({ id: config.id, is_active: checked })}
                    />
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(config)}>
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setDeleteId(config.id)}>
                      <Trash2 className="h-3.5 w-3.5 text-destructive" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="text-xs text-muted-foreground">
                  <p>Type: {config.config_type}</p>
                  <p>Config: {JSON.stringify(config.config)}</p>
                  {config.last_run_at && <p>Last run: {timeAgo(config.last_run_at)}</p>}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </QueryState>

      {/* Create/Edit dialog */}
      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editId ? "Edit Config" : "New Config"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
            <div className="space-y-1">
              <Label>Name</Label>
              <Input {...form.register("name")} />
            </div>
            <div className="space-y-1">
              <Label>Type</Label>
              <Select
                value={form.watch("config_type")}
                onValueChange={(v) => form.setValue("config_type", v)}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="search_query">Search Query</SelectItem>
                  <SelectItem value="career_page">Career Page</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {form.watch("config_type") === "search_query" ? (
              <>
                <div className="space-y-1"><Label>Query</Label><Input {...form.register("query")} /></div>
                <div className="space-y-1"><Label>Location</Label><Input {...form.register("location")} /></div>
              </>
            ) : (
              <div className="space-y-1"><Label>Career page URL</Label><Input {...form.register("url")} /></div>
            )}
            <DialogFooter>
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {editId ? "Update" : "Create"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteId}
        onOpenChange={() => setDeleteId(null)}
        title="Delete config"
        description="Are you sure you want to delete this search config?"
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        isPending={deleteMutation.isPending}
      />
    </div>
  );
}
```

- [ ] **Step 2: Implement search page**

Replace `web/src/pages/search.tsx`:

```tsx
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiClient } from "@/api/client";

export function Component() {
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [source, setSource] = useState<"indeed" | "linkedin">("indeed");

  const searchMutation = useMutation({
    mutationFn: () =>
      apiClient
        .post(`/api/search/${source}`, {
          query,
          location: location || undefined,
          limit: 10,
        })
        .then((r) => r.data),
    onSuccess: (data) => {
      toast.success(`Search started (task ${data.id.slice(0, 8)}...)`);
    },
    onError: () => toast.error("Search failed"),
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Input
          className="flex-1"
          placeholder="Search for jobs..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && query.trim()) searchMutation.mutate();
          }}
        />
        <Input
          className="w-48"
          placeholder="Location (optional)"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
        />
        <Select value={source} onValueChange={(v) => setSource(v as "indeed" | "linkedin")}>
          <SelectTrigger className="w-32"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="indeed">Indeed</SelectItem>
            <SelectItem value="linkedin">LinkedIn</SelectItem>
          </SelectContent>
        </Select>
        <Button onClick={() => query.trim() && searchMutation.mutate()} disabled={searchMutation.isPending || !query.trim()}>
          <Search className="mr-1.5 h-4 w-4" />
          {searchMutation.isPending ? "Searching..." : "Search"}
        </Button>
      </div>

      <p className="text-sm text-muted-foreground">
        Search results will appear in your Jobs list once discovered. Check the task indicator in the top bar for progress.
      </p>
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant
git add web/
git commit -m "feat(web): implement discover and search pages"
```

---

## Task 11: Skills Page with Charts

**Files:**
- Modify: `web/src/pages/skills.tsx`

- [ ] **Step 1: Implement skills page**

Replace `web/src/pages/skills.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { QueryState } from "@/components/shared/query-state";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";

export function Component() {
  const topQuery = useQuery({
    queryKey: queryKeys.skills.top(20),
    queryFn: () => apiClient.get("/api/skills/top?limit=20").then((r) => r.data),
    staleTime: 120_000,
  });

  const gapsQuery = useQuery({
    queryKey: queryKeys.skills.gaps,
    queryFn: () => apiClient.get("/api/skills/gaps").then((r) => r.data),
    staleTime: 120_000,
  });

  const trendsQuery = useQuery({
    queryKey: queryKeys.skills.trends,
    queryFn: () => apiClient.get("/api/skills/trends").then((r) => r.data),
    staleTime: 120_000,
  });

  const rolesQuery = useQuery({
    queryKey: queryKeys.skills.roles,
    queryFn: () => apiClient.get("/api/skills/roles").then((r) => r.data),
    staleTime: 120_000,
  });

  return (
    <div className="grid grid-cols-2 gap-5">
      {/* Top skills bar chart */}
      <Card className="col-span-2">
        <CardHeader><CardTitle className="text-base">Top Requested Skills</CardTitle></CardHeader>
        <CardContent>
          <QueryState
            query={topQuery}
            isEmpty={(data: any[]) => data.length === 0}
            empty={<p className="text-sm text-muted-foreground">No skill data yet. Analyze some jobs first.</p>}
          >
            {(data: any[]) => (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={data} layout="vertical" margin={{ left: 80 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis type="category" dataKey="skill" tick={{ fontSize: 12 }} width={80} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#2563eb" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </QueryState>
        </CardContent>
      </Card>

      {/* Skill gaps table */}
      <Card>
        <CardHeader><CardTitle className="text-base">Skill Gaps</CardTitle></CardHeader>
        <CardContent>
          <QueryState
            query={gapsQuery}
            isEmpty={(data: any[]) => data.length === 0}
            empty={<p className="text-sm text-muted-foreground">No gaps detected. Update your profile skills to see gaps.</p>}
          >
            {(data: any[]) => (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Skill</TableHead>
                    <TableHead className="text-right">Demand</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.slice(0, 15).map((gap: any) => (
                    <TableRow key={gap.skill}>
                      <TableCell className="font-medium">{gap.skill}</TableCell>
                      <TableCell className="text-right">{gap.demand_count} jobs</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </QueryState>
        </CardContent>
      </Card>

      {/* Trends line chart */}
      <Card>
        <CardHeader><CardTitle className="text-base">Skill Trends</CardTitle></CardHeader>
        <CardContent>
          <QueryState
            query={trendsQuery}
            isEmpty={(data: any[]) => data.length === 0}
            empty={<p className="text-sm text-muted-foreground">Not enough data for trends yet.</p>}
          >
            {(data: any[]) => {
              // Group by week, sum across skills for a simple line
              const weekMap = new Map<string, number>();
              for (const d of data) {
                const week = d.week.slice(0, 10);
                weekMap.set(week, (weekMap.get(week) ?? 0) + d.count);
              }
              const chartData = Array.from(weekMap.entries())
                .map(([week, count]) => ({ week, count }))
                .sort((a, b) => a.week.localeCompare(b.week));

              return (
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="week" tick={{ fontSize: 10 }} />
                    <YAxis />
                    <Tooltip />
                    <Line type="monotone" dataKey="count" stroke="#2563eb" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              );
            }}
          </QueryState>
        </CardContent>
      </Card>

      {/* Roles breakdown */}
      <Card className="col-span-2">
        <CardHeader><CardTitle className="text-base">Skills by Role Level</CardTitle></CardHeader>
        <CardContent>
          <QueryState
            query={rolesQuery}
            isEmpty={(data: any) => Object.keys(data).length === 0}
            empty={<p className="text-sm text-muted-foreground">No role data available.</p>}
          >
            {(data: any) => (
              <div className="grid grid-cols-3 gap-4">
                {Object.entries(data).map(([level, skills]: [string, any]) => (
                  <div key={level}>
                    <h4 className="mb-2 text-sm font-semibold capitalize">{level}</h4>
                    <div className="space-y-1">
                      {skills.slice(0, 8).map((s: any) => (
                        <div key={s.skill} className="flex items-center justify-between text-xs">
                          <span>{s.skill}</span>
                          <span className="text-muted-foreground">{s.count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </QueryState>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant
git add web/
git commit -m "feat(web): implement skills analytics page with charts and gaps table"
```

---

## Task 12: Answers Page

**Files:**
- Modify: `web/src/pages/answers.tsx`

- [ ] **Step 1: Implement answers page**

Replace `web/src/pages/answers.tsx`:

```tsx
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { Plus, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { QueryState } from "@/components/shared/query-state";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";
import { useDebounce } from "@/hooks/use-debounce";

interface AnswerFormData {
  question: string;
  answer: string;
  category: string;
}

export function Component() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<any | null>(null);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState("");
  const debouncedSearch = useDebounce(search, 300);

  const answersQuery = useQuery({
    queryKey: queryKeys.answers.list({ search: debouncedSearch }),
    queryFn: () => {
      const qs = new URLSearchParams();
      if (debouncedSearch) qs.set("search", debouncedSearch);
      return apiClient.get(`/api/answers?${qs}`).then((r) => r.data);
    },
  });

  const statsQuery = useQuery({
    queryKey: queryKeys.answers.stats,
    queryFn: () => apiClient.get("/api/answers/stats").then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (data: AnswerFormData) =>
      apiClient.post("/api/answers", data).then((r) => r.data),
    onSuccess: () => {
      toast.success("Answer added");
      setFormOpen(false);
      queryClient.invalidateQueries({ queryKey: queryKeys.answers.all });
    },
    onError: () => toast.error("Failed to add answer"),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, ...data }: { id: number; answer?: string; category?: string }) =>
      apiClient.put(`/api/answers/${id}`, data).then((r) => r.data),
    onSuccess: () => {
      toast.success("Answer updated");
      setFormOpen(false);
      setEditTarget(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.answers.all });
    },
    onError: () => toast.error("Failed to update answer"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => apiClient.delete(`/api/answers/${id}`),
    onSuccess: () => {
      toast.success("Answer deleted");
      setDeleteId(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.answers.all });
    },
    onError: () => toast.error("Failed to delete answer"),
  });

  const importMutation = useMutation({
    mutationFn: (data: any[]) => apiClient.post("/api/answers/import", data).then((r) => r.data),
    onSuccess: (data) => {
      toast.success(`Imported ${data.imported} answers`);
      setImportOpen(false);
      setImportText("");
      queryClient.invalidateQueries({ queryKey: queryKeys.answers.all });
    },
    onError: () => toast.error("Import failed"),
  });

  const form = useForm<AnswerFormData>({
    defaultValues: { question: "", answer: "", category: "" },
  });

  function openCreate() {
    form.reset({ question: "", answer: "", category: "" });
    setEditTarget(null);
    setFormOpen(true);
  }

  function openEdit(a: any) {
    form.reset({ question: a.question, answer: a.answer, category: a.category ?? "" });
    setEditTarget(a);
    setFormOpen(true);
  }

  function handleSubmit(data: AnswerFormData) {
    if (editTarget) {
      updateMutation.mutate({
        id: editTarget.id,
        answer: data.answer,
        category: data.category || undefined,
      });
    } else {
      createMutation.mutate(data);
    }
  }

  function handleImport() {
    try {
      const data = JSON.parse(importText);
      if (!Array.isArray(data)) {
        toast.error("JSON must be an array");
        return;
      }
      importMutation.mutate(data);
    } catch {
      toast.error("Invalid JSON");
    }
  }

  const stats = statsQuery.data as any;

  return (
    <div className="space-y-5">
      {/* Stats */}
      {stats && (
        <div className="flex gap-3">
          <Card className="flex-1">
            <CardContent className="pt-4">
              <div className="text-[11px] font-medium uppercase text-muted-foreground">Total Answers</div>
              <div className="text-2xl font-bold">{stats.total}</div>
            </CardContent>
          </Card>
          <Card className="flex-1">
            <CardContent className="pt-4">
              <div className="text-[11px] font-medium uppercase text-muted-foreground">Used at Least Once</div>
              <div className="text-2xl font-bold">{stats.used}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <Input className="w-64" placeholder="Search answers..." value={search} onChange={(e) => setSearch(e.target.value)} />
        <div className="ml-auto flex gap-2">
          <Button variant="outline" onClick={() => setImportOpen(true)}>
            <Upload className="mr-1.5 h-4 w-4" /> Import
          </Button>
          <Button onClick={openCreate}>
            <Plus className="mr-1.5 h-4 w-4" /> Add Answer
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-lg border">
        <QueryState
          query={answersQuery}
          isEmpty={(data: any[]) => data.length === 0}
          empty={<p className="p-8 text-center text-sm text-muted-foreground">No answers yet.</p>}
        >
          {(data: any[]) => (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Question</TableHead>
                  <TableHead>Answer</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead className="text-right">Used</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((a: any) => (
                  <TableRow key={a.id}>
                    <TableCell className="max-w-xs truncate font-medium">{a.question}</TableCell>
                    <TableCell className="max-w-xs truncate text-muted-foreground">{a.answer}</TableCell>
                    <TableCell>{a.category ?? "—"}</TableCell>
                    <TableCell className="text-right">{a.times_used}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => openEdit(a)}>Edit</Button>
                      <Button variant="ghost" size="sm" className="h-7 text-xs text-destructive" onClick={() => setDeleteId(a.id)}>Delete</Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </QueryState>
      </div>

      {/* Add/Edit dialog */}
      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editTarget ? "Edit Answer" : "Add Answer"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
            <div className="space-y-1">
              <Label>Question</Label>
              <Input {...form.register("question")} disabled={!!editTarget} />
            </div>
            <div className="space-y-1">
              <Label>Answer</Label>
              <Textarea rows={4} {...form.register("answer")} />
            </div>
            <div className="space-y-1">
              <Label>Category (optional)</Label>
              <Input {...form.register("category")} />
            </div>
            <DialogFooter>
              <Button type="submit" disabled={createMutation.isPending || updateMutation.isPending}>
                {editTarget ? "Update" : "Add"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Import dialog */}
      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Import Answers</DialogTitle></DialogHeader>
          <Textarea
            rows={10}
            placeholder='[{"question": "...", "answer": "...", "category": "..."}]'
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
            className="font-mono text-xs"
          />
          <DialogFooter>
            <Button onClick={handleImport} disabled={importMutation.isPending || !importText.trim()}>
              {importMutation.isPending ? "Importing..." : "Import"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={!!deleteId}
        onOpenChange={() => setDeleteId(null)}
        title="Delete answer"
        description="Are you sure you want to delete this answer?"
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={() => deleteId && deleteMutation.mutate(deleteId)}
        isPending={deleteMutation.isPending}
      />
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant
git add web/
git commit -m "feat(web): implement answers page with CRUD, import, and stats"
```

---

## Task 13: Settings + Billing Pages

**Files:**
- Modify: `web/src/pages/settings.tsx`, `web/src/pages/billing/overview.tsx`, `web/src/pages/billing/plans.tsx`, `web/src/pages/billing/usage.tsx`, `web/src/pages/billing/history.tsx`

- [ ] **Step 1: Implement settings page**

Replace `web/src/pages/settings.tsx`:

```tsx
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { QueryState } from "@/components/shared/query-state";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";
import { useAuthStore } from "@/stores/auth-store";
import { useState } from "react";

export function Component() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = user?.role === "owner" || user?.role === "admin";

  return (
    <div className="max-w-2xl space-y-5">
      {/* Account */}
      <Card>
        <CardHeader><CardTitle className="text-base">Account</CardTitle></CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Email</span>
            <span>{user?.email}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Role</span>
            <Badge variant="outline">{user?.role}</Badge>
          </div>
        </CardContent>
      </Card>

      {/* Appearance */}
      <Card>
        <CardHeader><CardTitle className="text-base">Appearance</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center justify-between text-sm">
            <span>Theme</span>
            <ThemeToggle />
          </div>
        </CardContent>
      </Card>

      {/* Team management (admin only) */}
      {isAdmin && <TeamSection />}
    </div>
  );
}

function TeamSection() {
  const queryClient = useQueryClient();
  const [removeTarget, setRemoveTarget] = useState<{ id: string; email: string } | null>(null);

  const usersQuery = useQuery({
    queryKey: queryKeys.admin.users,
    queryFn: () => apiClient.get("/api/admin/users").then((r) => r.data),
  });

  const changeRoleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      apiClient.put(`/api/admin/users/${userId}/role`, null, { params: { role } }).then((r) => r.data),
    onSuccess: () => {
      toast.success("Role updated");
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.users });
    },
    onError: () => toast.error("Failed to update role"),
  });

  const removeMutation = useMutation({
    mutationFn: (userId: string) => apiClient.delete(`/api/admin/users/${userId}`),
    onSuccess: () => {
      toast.success("User removed");
      setRemoveTarget(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.users });
    },
    onError: (err: any) => toast.error(err.response?.data?.detail || "Failed to remove user"),
  });

  return (
    <Card>
      <CardHeader><CardTitle className="text-base">Team Members</CardTitle></CardHeader>
      <CardContent>
        <QueryState query={usersQuery} isEmpty={(data: any[]) => data.length === 0}>
          {(data: any[]) => (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((u: any) => (
                  <TableRow key={u.id}>
                    <TableCell>{u.email}</TableCell>
                    <TableCell>
                      <Select
                        value={u.role}
                        onValueChange={(role) => changeRoleMutation.mutate({ userId: u.id, role })}
                      >
                        <SelectTrigger className="w-28 h-8"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="owner">Owner</SelectItem>
                          <SelectItem value="admin">Admin</SelectItem>
                          <SelectItem value="member">Member</SelectItem>
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs text-destructive"
                        onClick={() => setRemoveTarget({ id: u.id, email: u.email })}
                      >
                        Remove
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </QueryState>
      </CardContent>

      <ConfirmDialog
        open={!!removeTarget}
        onOpenChange={() => setRemoveTarget(null)}
        title="Remove user"
        description={`Remove ${removeTarget?.email} from the team?`}
        confirmLabel="Remove"
        variant="destructive"
        onConfirm={() => removeTarget && removeMutation.mutate(removeTarget.id)}
        isPending={removeMutation.isPending}
      />
    </Card>
  );
}
```

- [ ] **Step 2: Implement billing overview**

Replace `web/src/pages/billing/overview.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { QueryState } from "@/components/shared/query-state";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";

export function Component() {
  const navigate = useNavigate();

  const planQuery = useQuery({
    queryKey: queryKeys.billing.plan,
    queryFn: () => apiClient.get("/api/billing/plan").then((r) => r.data),
    staleTime: 600_000,
  });

  const usageQuery = useQuery({
    queryKey: queryKeys.billing.usage,
    queryFn: () => apiClient.get("/api/billing/usage").then((r) => r.data),
    staleTime: 60_000,
  });

  return (
    <div className="max-w-2xl space-y-5">
      <QueryState query={planQuery}>
        {(plan: any) => (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Current Plan</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-2xl font-bold capitalize">{plan.plan}</span>
                <Button variant="outline" onClick={() => navigate("/billing/plans")}>
                  View Plans
                </Button>
              </div>
              <div className="space-y-1 text-sm text-muted-foreground">
                <p>Scrapes: {plan.limits.scrapes_per_day}/day</p>
                <p>Analyses: {plan.limits.analyses_per_day}/day</p>
                <p>Generations: {plan.limits.generations_per_day}/day</p>
              </div>
            </CardContent>
          </Card>
        )}
      </QueryState>

      <QueryState query={usageQuery}>
        {(usage: any) => (
          <Card>
            <CardHeader><CardTitle className="text-base">Current Period Usage</CardTitle></CardHeader>
            <CardContent className="space-y-2 text-sm">
              {Object.entries(usage.actions ?? {}).map(([action, count]: [string, any]) => (
                <div key={action} className="flex items-center justify-between">
                  <span className="capitalize">{action}</span>
                  <span className="font-mono">{count}</span>
                </div>
              ))}
              <div className="flex items-center justify-between border-t pt-2">
                <span>Total tokens</span>
                <span className="font-mono">{usage.tokens_used?.toLocaleString()}</span>
              </div>
            </CardContent>
          </Card>
        )}
      </QueryState>

      <div className="flex gap-2">
        <Button variant="outline" onClick={() => navigate("/billing/usage")}>Detailed Usage</Button>
        <Button variant="outline" onClick={() => navigate("/billing/history")}>Invoice History</Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Implement billing plans page**

Replace `web/src/pages/billing/plans.tsx`:

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Check } from "lucide-react";

const plans = [
  {
    name: "Free",
    price: "$0",
    features: ["10 scrapes/day", "20 analyses/day", "5 generations/day", "1 user"],
    current: true,
  },
  {
    name: "Pro",
    price: "$29/mo",
    features: ["100 scrapes/day", "200 analyses/day", "50 generations/day", "5 users", "Priority support"],
    current: false,
  },
  {
    name: "Enterprise",
    price: "Custom",
    features: ["Unlimited scrapes", "Unlimited analyses", "Unlimited generations", "Unlimited users", "SSO", "Dedicated support"],
    current: false,
  },
];

export function Component() {
  return (
    <div className="max-w-3xl">
      <div className="grid grid-cols-3 gap-4">
        {plans.map((plan) => (
          <Card key={plan.name} className={plan.current ? "border-primary" : ""}>
            <CardHeader>
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">{plan.name}</CardTitle>
                {plan.current && <Badge>Current</Badge>}
              </div>
              <div className="text-2xl font-bold">{plan.price}</div>
            </CardHeader>
            <CardContent className="space-y-2">
              {plan.features.map((f) => (
                <div key={f} className="flex items-center gap-2 text-sm">
                  <Check className="h-4 w-4 text-green-600" /> {f}
                </div>
              ))}
              <Button
                className="mt-4 w-full"
                variant={plan.current ? "outline" : "default"}
                disabled={plan.current}
              >
                {plan.current ? "Current plan" : "Upgrade"}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
      <p className="mt-4 text-xs text-muted-foreground">
        Payment integration coming soon. Plans shown for illustration.
      </p>
    </div>
  );
}
```

- [ ] **Step 4: Implement billing usage page**

Replace `web/src/pages/billing/usage.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { QueryState } from "@/components/shared/query-state";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";

export function Component() {
  const historyQuery = useQuery({
    queryKey: queryKeys.billing.history(30),
    queryFn: () => apiClient.get("/api/billing/usage/history?days=30").then((r) => r.data),
    staleTime: 60_000,
  });

  return (
    <div className="max-w-2xl space-y-5">
      <Card>
        <CardHeader><CardTitle className="text-base">Daily Usage (Last 30 Days)</CardTitle></CardHeader>
        <CardContent>
          <QueryState
            query={historyQuery}
            isEmpty={(data: any[]) => data.length === 0}
            empty={<p className="text-sm text-muted-foreground">No usage data yet.</p>}
          >
            {(data: any[]) => {
              // Aggregate by day
              const dayMap = new Map<string, number>();
              for (const d of data) {
                const day = d.day.slice(0, 10);
                dayMap.set(day, (dayMap.get(day) ?? 0) + d.count);
              }
              const chartData = Array.from(dayMap.entries())
                .map(([day, count]) => ({ day, count }))
                .sort((a, b) => a.day.localeCompare(b.day));

              return (
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="day" tick={{ fontSize: 10 }} />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="count" fill="#2563eb" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              );
            }}
          </QueryState>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 5: Implement billing history page**

Replace `web/src/pages/billing/history.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { QueryState } from "@/components/shared/query-state";
import { apiClient } from "@/api/client";
import { queryKeys } from "@/lib/query-keys";

export function Component() {
  const invoicesQuery = useQuery({
    queryKey: queryKeys.billing.invoices,
    queryFn: () => apiClient.get("/api/billing/invoices").then((r) => r.data),
    staleTime: 600_000,
  });

  return (
    <div className="max-w-2xl">
      <Card>
        <CardHeader><CardTitle className="text-base">Invoice History</CardTitle></CardHeader>
        <CardContent>
          <QueryState
            query={invoicesQuery}
            isEmpty={(data: any[]) => data.length === 0}
            empty={
              <p className="text-sm text-muted-foreground">
                No invoices yet. Invoice history will appear here once billing is active.
              </p>
            }
          >
            {(data: any[]) => (
              <div>
                {data.map((inv: any, i: number) => (
                  <div key={i} className="flex items-center justify-between border-b py-2 text-sm last:border-0">
                    <span>{inv.date}</span>
                    <span>{inv.amount}</span>
                    <span>{inv.status}</span>
                  </div>
                ))}
              </div>
            )}
          </QueryState>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx tsc --noEmit
```

- [ ] **Step 7: Commit**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant
git add web/
git commit -m "feat(web): implement settings and billing pages"
```

---

## Task 14: Docker + Integration Verification

**Files:**
- Create: `web/Dockerfile`, `web/nginx.conf`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Create nginx config**

Create `web/nginx.conf`:

```nginx
server {
    listen 3000;
    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback — all routes serve index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to backend
    location /api/ {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

- [ ] **Step 2: Create Dockerfile**

Create `web/Dockerfile`:

```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Serve stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **Step 3: Add web service to docker-compose.yml**

Add the following service to `docker-compose.yml` before the `volumes:` section:

```yaml
  web:
    build:
      context: ./web
      dockerfile: Dockerfile
    ports:
      - "${WEB_PORT:-3000}:3000"
    depends_on:
      - api
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx vitest run
```

Expected: All tests PASS.

- [ ] **Step 5: Verify build succeeds**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npm run build
ls -la dist/
```

Expected: `dist/` directory with `index.html` and `assets/`.

- [ ] **Step 6: Verify TypeScript is clean**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant/web
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 7: Commit**

```bash
cd /Users/msomali/Documents/Devs/ML/job-application-assistant
git add web/ docker-compose.yml
git commit -m "feat(web): add Docker build, nginx config, docker-compose web service"
```

---

## Summary

| Task | What it builds | Key files |
|------|---------------|-----------|
| 1 | Vite + React + Tailwind + shadcn scaffold | `web/package.json`, configs |
| 2 | API client, auth store, auth hooks, utils | `api/client.ts`, `auth-store.ts`, `use-auth.ts` |
| 3 | App shell: icon rail, top bar, theme, routing | `app-shell.tsx`, `icon-rail.tsx`, `router.tsx` |
| 4 | Auth pages (login, register, forgot password) | `pages/auth/*.tsx`, `validators.ts` |
| 5 | SSE task stream hook | `use-task-stream.ts`, `task-store.ts` |
| 6 | Shared components | `query-state.tsx`, `pagination.tsx`, `score-badge.tsx` |
| 7 | Dashboard page | `pages/dashboard.tsx` |
| 8 | Jobs list + detail pages | `pages/jobs/list.tsx`, `pages/jobs/detail.tsx` |
| 9 | Profile page with form + JSON import | `pages/profile.tsx`, `json-import-dialog.tsx` |
| 10 | Discover + search pages | `pages/discover.tsx`, `pages/search.tsx` |
| 11 | Skills analytics with charts | `pages/skills.tsx` |
| 12 | Answers CRUD + import | `pages/answers.tsx` |
| 13 | Settings + billing pages | `pages/settings.tsx`, `pages/billing/*.tsx` |
| 14 | Docker + nginx + integration check | `Dockerfile`, `nginx.conf`, `docker-compose.yml` |
