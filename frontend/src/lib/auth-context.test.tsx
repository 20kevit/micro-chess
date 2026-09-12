import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { AuthProvider, useAuth } from "./auth-context";
import { api, clearToken, getToken, setToken } from "../api/client";
import type { AuthUser } from "../api/types";

vi.mock("../api/client", async (importOriginal) => {
  const orig = await importOriginal<typeof import("../api/client")>();
  return { ...orig, api: {} };
});
const mockedApi = vi.mocked(api, true);

function fail(status: number, code: string, detail: string): Error {
  return Object.assign(new Error(`api_error:${status}:${detail}`), { status, code, detail });
}

const USER: AuthUser = {
  id: 1,
  username: "kid_01",
  display_name: "kid_01",
  roles: ["PLAYER"],
  active_role: "PLAYER",
  created_at: "2026-01-01T00:00:00",
};

function Consumer() {
  const { user, loading, error, login, logout } = useAuth();
  return (
    <div>
      <span data-testid="loading">{loading ? "loading" : "ready"}</span>
      <span data-testid="user">{user ? user.username : "anonymous"}</span>
      <span data-testid="error">{error}</span>
      <button type="button" onClick={() => void login("kid_01", "secret123")}>
        login-btn
      </button>
      <button type="button" onClick={() => void logout()}>
        logout-btn
      </button>
    </div>
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  clearToken();
  mockedApi.me = vi.fn();
  mockedApi.login = vi.fn();
  mockedApi.register = vi.fn();
  mockedApi.logout = vi.fn().mockResolvedValue(undefined);
});

describe("AuthProvider", () => {
  it("loads the current user when a token is stored", async () => {
    setToken("tok");
    mockedApi.me = vi.fn().mockResolvedValue(USER);
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("user").textContent).toBe("kid_01"));
    expect(screen.getByTestId("loading").textContent).toBe("ready");
  });

  it("drops revoked tokens and falls back to anonymous", async () => {
    setToken("stale");
    mockedApi.me = vi.fn().mockRejectedValue(fail(401, "AUTH_REQUIRED", "auth_required"));
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("ready"));
    expect(screen.getByTestId("user").textContent).toBe("anonymous");
    expect(getToken()).toBeNull();
  });

  it("login stores the token and synchronizes the user", async () => {
    const user = userEvent.setup();
    mockedApi.login = vi.fn().mockResolvedValue({ access_token: "new-tok", token_type: "bearer" });
    mockedApi.me = vi.fn().mockResolvedValue(USER);
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );
    await user.click(screen.getByRole("button", { name: "login-btn" }));
    await waitFor(() => expect(screen.getByTestId("user").textContent).toBe("kid_01"));
    expect(getToken()).toBe("new-tok");
    expect(mockedApi.login).toHaveBeenCalledWith({ username: "kid_01", password: "secret123" });
  });

  it("logout ends the session locally even when the request fails", async () => {
    const user = userEvent.setup();
    setToken("tok");
    mockedApi.me = vi.fn().mockResolvedValue(USER);
    mockedApi.logout = vi.fn().mockRejectedValue(fail(500, "INTERNAL_ERROR", "internal_error"));
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("user").textContent).toBe("kid_01"));
    await user.click(screen.getByRole("button", { name: "logout-btn" }));
    await waitFor(() => expect(screen.getByTestId("user").textContent).toBe("anonymous"));
    expect(getToken()).toBeNull();
  });

  it("switchRole delegates to the server and reloads the session user", async () => {
    const user = userEvent.setup();
    setToken("tok");
    const coach: AuthUser = { ...USER, roles: ["PLAYER", "COACH"], active_role: "COACH" };
    mockedApi.me = vi
      .fn()
      .mockResolvedValueOnce(USER)
      .mockResolvedValue(coach);
    mockedApi.switchActiveRole = vi
      .fn()
      .mockResolvedValue({ active_role: "COACH", roles: ["PLAYER", "COACH"] });
    function SwitchConsumer() {
      const { user: current, switchRole } = useAuth();
      return (
        <div>
          <span data-testid="active">{current ? current.active_role : "anonymous"}</span>
          <button type="button" onClick={() => void switchRole("COACH")}>
            switch-btn
          </button>
        </div>
      );
    }
    render(
      <AuthProvider>
        <SwitchConsumer />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("active").textContent).toBe("PLAYER"));
    await user.click(screen.getByRole("button", { name: "switch-btn" }));
    await waitFor(() => expect(screen.getByTestId("active").textContent).toBe("COACH"));
    expect(mockedApi.switchActiveRole).toHaveBeenCalledWith("COACH");
  });
});
