import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { AccountPage } from "./AccountPage";
import { RequireAuth } from "../lib/require-auth";
import { LoginPage } from "./LoginPage";
import { useAuth } from "../lib/auth-context";
import type { AuthUser } from "../api/types";

vi.mock("../lib/auth-context", () => ({ useAuth: vi.fn() }));
const mockedUseAuth = vi.mocked(useAuth);

const USER: AuthUser = {
  id: 7,
  username: "kid_01",
  display_name: "kid_01",
  roles: ["PLAYER", "COACH"],
  created_at: "2026-01-01T00:00:00",
};

function base(overrides: object = {}) {
  return {
    user: null,
    loading: false,
    error: "",
    login: vi.fn().mockResolvedValue(undefined),
    register: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
    refresh: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  } as ReturnType<typeof useAuth>;
}

beforeEach(() => {
  vi.resetAllMocks();
});

describe("protected account route", () => {
  it("redirects anonymous visitors to login", async () => {
    mockedUseAuth.mockReturnValue(base({ user: null }));
    render(
      <MemoryRouter initialEntries={["/account"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/account"
            element={
              <RequireAuth>
                <AccountPage />
              </RequireAuth>
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText("ورود به میکروچس")).toBeTruthy());
  });

  it("shows the server-owned identity with Persian roles", () => {
    mockedUseAuth.mockReturnValue(base({ user: USER }));
    render(
      <MemoryRouter initialEntries={["/account"]}>
        <Routes>
          <Route
            path="/account"
            element={
              <RequireAuth>
                <AccountPage />
              </RequireAuth>
            }
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("حساب من")).toBeTruthy();
    expect(screen.getByText("kid_01")).toBeTruthy();
    // Roles render joined in one line ("بازیکن، مربی"); match the whole line
    // so the "پروفایل بازیکن" button never collides.
    expect(screen.getByText("نقش‌ها: بازیکن، مربی")).toBeTruthy();
  });

  it("logout returns to the home screen", async () => {
    const user = userEvent.setup();
    const logout = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue(base({ user: USER, logout }));
    render(
      <MemoryRouter initialEntries={["/account"]}>
        <Routes>
          <Route path="/" element={<div>home-dummy</div>} />
          <Route path="/account" element={<AccountPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await user.click(screen.getByRole("button", { name: "خروج" }));
    await waitFor(() => expect(screen.getByText("home-dummy")).toBeTruthy());
    expect(logout).toHaveBeenCalled();
  });
});
