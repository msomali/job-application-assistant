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
