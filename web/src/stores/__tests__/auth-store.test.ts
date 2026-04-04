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
