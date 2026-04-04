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
  const resp = await apiClient.get("/api/users/me");
  return resp.data;
}

export function useLogin() {
  const setAuth = useAuthStore((s) => s.setAuth);

  return useMutation({
    mutationFn: async (creds: LoginCredentials) => {
      const form = new URLSearchParams();
      form.append("username", creds.email);
      form.append("password", creds.password);

      const resp = await apiClient.post("/api/auth/login", form, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });
      const token = resp.data.access_token;

      useAuthStore.getState().setAuth(token, { id: "", email: creds.email, tenant_id: "", role: "" });

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
