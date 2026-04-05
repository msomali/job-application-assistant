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
