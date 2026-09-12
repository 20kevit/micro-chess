import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProfilePage } from "./ProfilePage";
import { useAuth } from "../lib/auth-context";
import { api } from "../api/client";

vi.mock("../lib/auth-context", () => ({ useAuth: vi.fn() }));
vi.mock("../api/client", () => ({
  api: {
    getProfile: vi.fn(),
    updateProfile: vi.fn(),
    listIdentities: vi.fn(),
    addIdentity: vi.fn(),
    updateIdentity: vi.fn(),
    deleteIdentity: vi.fn(),
  },
  apiStatus: (e: unknown) =>
    e instanceof Error && typeof (e as unknown as { status?: unknown }).status === "number"
      ? (e as unknown as { status: number }).status
      : null,
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedApi = vi.mocked(api, true);

function auth() {
  mockedUseAuth.mockReturnValue({
    user: { id: 1, username: "kid_01", display_name: "kid_01", roles: ["PLAYER"], active_role: "PLAYER", created_at: "" },
    loading: false,
    error: "",
    login: vi.fn().mockResolvedValue(undefined),
    register: vi.fn().mockResolvedValue(undefined),
    switchRole: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
    refresh: vi.fn().mockResolvedValue(undefined),
  } as ReturnType<typeof useAuth>);
}

beforeEach(() => {
  vi.resetAllMocks();
  auth();
  mockedApi.getProfile.mockResolvedValue({
    display_name: "kid_01",
    bio: "",
    avatar_reference: "",
    updated_at: null,
  });
  mockedApi.listIdentities.mockResolvedValue([]);
});

function renderPage() {
  render(
    <MemoryRouter>
      <ProfilePage />
    </MemoryRouter>,
  );
}

describe("profile page", () => {
  it("renders the server profile and saves edits", async () => {
    const user = userEvent.setup();
    mockedApi.updateProfile.mockResolvedValue({
      display_name: "Omid",
      bio: "hi",
      avatar_reference: "",
      updated_at: null,
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("پروفایل بازیکن")).toBeTruthy());

    await user.clear(screen.getByLabelText("نام نمایشی"));
    await user.type(screen.getByLabelText("نام نمایشی"), "Omid");
    await user.click(screen.getByRole("button", { name: "ذخیره" }));
    await waitFor(() =>
      expect(mockedApi.updateProfile).toHaveBeenCalledWith({ display_name: "Omid", bio: "" }),
    );
    expect(screen.getByText("ذخیره شد.")).toBeTruthy();
  });

  it("adds an identity and surfaces duplicate conflicts in Persian", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() => expect(screen.getByText("هویت‌های شطرنجی")).toBeTruthy());
    expect(screen.getByText("هنوز هویتی وصل نکرده‌ای.")).toBeTruthy();

    mockedApi.addIdentity.mockResolvedValue({
      id: 3,
      provider: "lichess",
      username: "omid",
      rating: null,
      rating_type: null,
      is_verified: false,
    });
    await user.type(screen.getByLabelText("نام کاربری"), "omid");
    await user.click(screen.getByRole("button", { name: "افزودن هویت" }));
    await waitFor(() =>
      expect(mockedApi.addIdentity).toHaveBeenCalledWith({
        provider: "lichess",
        username: "omid",
        rating: null,
        rating_type: null,
      }),
    );
    expect(screen.getByText("omid")).toBeTruthy();
    expect(screen.getByText("تأییدنشده")).toBeTruthy();

    const conflict = new Error("api_error:409") as Error & { status: number };
    conflict.status = 409;
    mockedApi.addIdentity.mockRejectedValue(conflict);
    await user.click(screen.getByRole("button", { name: "افزودن هویت" }));
    await waitFor(() => expect(screen.getByText("این هویت قبلاً وصل شده است.")).toBeTruthy());
  });

  it("shows loading and retry states", async () => {
    mockedApi.getProfile.mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(screen.getByText("در حال بارگذاری…")).toBeTruthy();
  });
});
