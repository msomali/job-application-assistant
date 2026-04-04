import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/api/client", () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

import { apiClient } from "@/api/client";
import { useAuthStore } from "@/stores/auth-store";

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

    const loginResp = await apiClient.post("/api/auth/login", new URLSearchParams({
      username: "a@b.com",
      password: "pass123",
    }));
    const token = loginResp.data.access_token;

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
