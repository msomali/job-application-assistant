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
