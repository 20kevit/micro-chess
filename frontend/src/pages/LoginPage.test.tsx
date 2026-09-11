import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { LoginPage } from "./LoginPage";
import { useAuth } from "../lib/auth-context";

vi.mock("../lib/auth-context", () => ({ useAuth: vi.fn() }));
const mockedUseAuth = vi.mocked(useAuth);

function state(overrides: Partial<ReturnType<typeof useAuth>> = {}) {
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

function renderPage(initial = "/login") {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<div>register-dummy</div>} />
        <Route path="/account" element={<div>account-dummy</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function fail(status: number, code: string, detail: string): Error {
  return Object.assign(new Error(`api_error:${status}:${detail}`), { status, code, detail });
}

beforeEach(() => {
  vi.resetAllMocks();
  mockedUseAuth.mockReturnValue(state());
});

describe("LoginPage", () => {
  it("renders the Persian form and submits trimmed credentials", async () => {
    const user = userEvent.setup();
    const login = vi.fn().mockResolvedValue(undefined);
    mockedUseAuth.mockReturnValue(state({ login }));
    renderPage();
    expect(screen.getByText("ورود به میکروچس")).toBeTruthy();
    await user.type(screen.getByLabelText("نام کاربری"), "  Kid_01 ");
    await user.type(screen.getByLabelText("گذرواژه"), "secret123");
    await user.click(screen.getByRole("button", { name: "وارد شو" }));
    expect(login).toHaveBeenCalledWith("Kid_01", "secret123");
  });

  it("shows a Persian error on invalid credentials and keeps the input", async () => {
    const user = userEvent.setup();
    const login = vi.fn().mockRejectedValue(fail(401, "INVALID_CREDENTIALS", "invalid_credentials"));
    mockedUseAuth.mockReturnValue(state({ login }));
    renderPage();
    await user.type(screen.getByLabelText("نام کاربری"), "kid_01");
    await user.click(screen.getByRole("button", { name: "وارد شو" }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(screen.getByRole("alert").textContent).toBe("نام کاربری یا گذرواژه درست نیست.");
    expect((screen.getByLabelText("نام کاربری") as HTMLInputElement).value).toBe("kid_01");
  });

  it("redirects authenticated users to the destination", async () => {
    mockedUseAuth.mockReturnValue(
      state({
        user: {
          id: 1,
          username: "kid_01",
          display_name: "kid_01",
          roles: ["PLAYER"],
          created_at: "",
        },
      }),
    );
    renderPage();
    await waitFor(() => expect(screen.getByText("account-dummy")).toBeTruthy());
  });
});
