import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RelationshipsPage } from "./RelationshipsPage";
import { useAuth } from "../lib/auth-context";
import { relationshipsApi } from "../api/client";
import type { Relationship } from "../api/types";

vi.mock("../lib/auth-context", () => ({ useAuth: vi.fn() }));
vi.mock("../api/client", () => ({
  relationshipsApi: { list: vi.fn(), create: vi.fn(), accept: vi.fn(), revoke: vi.fn() },
  apiDetail: () => "",
}));

const mockedUseAuth = vi.mocked(useAuth);
const mockedRel = vi.mocked(relationshipsApi, true);

function auth() {
  mockedUseAuth.mockReturnValue({
    user: { id: 9, username: "kid_01", display_name: "kid_01", roles: ["PLAYER"], active_role: "PLAYER", created_at: "" },
    loading: false,
    error: "",
    login: vi.fn().mockResolvedValue(undefined),
    register: vi.fn().mockResolvedValue(undefined),
    switchRole: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
    refresh: vi.fn().mockResolvedValue(undefined),
  } as ReturnType<typeof useAuth>);
}

const pendingIn: Relationship = {
  id: 1,
  kind: "coach",
  status: "pending",
  mentor_user_id: 3,
  student_user_id: 9,
  other_user_id: 3,
  other_username: "coach_a",
  other_display_name: "Coach A",
  created_by_user_id: 3,
  created_at: "",
  accepted_at: null,
  revoked_at: null,
};

const activeRow: Relationship = {
  id: 2,
  kind: "parent",
  status: "active",
  mentor_user_id: 4,
  student_user_id: 9,
  other_user_id: 4,
  other_username: "parent_a",
  other_display_name: "Parent A",
  created_by_user_id: 4,
  created_at: "",
  accepted_at: "",
  revoked_at: null,
};

beforeEach(() => {
  vi.resetAllMocks();
  auth();
});

function renderPage() {
  render(
    <MemoryRouter>
      <RelationshipsPage />
    </MemoryRouter>,
  );
}

describe("relationships page", () => {
  it("renders Persian title, pending requests, and active edges", async () => {
    mockedRel.list.mockResolvedValue([pendingIn, activeRow]);
    renderPage();
    await waitFor(() => expect(screen.getByText("روابط من")).toBeTruthy());
    expect(screen.getByText("در انتظار تأیید تو")).toBeTruthy();
    expect(screen.getByText("coach_a")).toBeTruthy();
    expect(screen.getByText("parent_a")).toBeTruthy();
    expect(screen.getByText("مربی می‌تواند پیشرفت، تمرین‌ها، امتیاز و تحلیل تو را ببیند.")).toBeTruthy();
  });

  it("shows an empty state when there are no relationships", async () => {
    mockedRel.list.mockResolvedValue([]);
    renderPage();
    await waitFor(() => expect(screen.getByText("هنوز رابطه‌ای نداری.")).toBeTruthy());
  });

  it("sends an invitation by username", async () => {
    const user = userEvent.setup();
    mockedRel.list.mockResolvedValue([]);
    mockedRel.create.mockResolvedValue({ ...pendingIn, created_by_user_id: 9 });
    renderPage();
    await waitFor(() => expect(screen.getByText("هنوز رابطه‌ای نداری.")).toBeTruthy());
    await user.type(screen.getByLabelText("نام کاربری طرف مقابل"), "coach_a");
    await user.click(screen.getByText("ارسال درخواست"));
    await waitFor(() => expect(mockedRel.create).toHaveBeenCalledWith({ kind: "coach", other_username: "coach_a" }));
  });

  it("accepts an incoming request", async () => {
    const user = userEvent.setup();
    mockedRel.list.mockResolvedValue([pendingIn]);
    mockedRel.accept.mockResolvedValue({ ...pendingIn, status: "active" });
    renderPage();
    await waitFor(() => expect(screen.getByText("تأیید")).toBeTruthy());
    await user.click(screen.getByText("تأیید"));
    await waitFor(() => expect(mockedRel.accept).toHaveBeenCalledWith(1));
  });

  it("revokes an active edge after confirmation", async () => {
    const user = userEvent.setup();
    mockedRel.list.mockResolvedValue([activeRow]);
    mockedRel.revoke.mockResolvedValue({ ...activeRow, status: "revoked" });
    vi.stubGlobal("confirm", vi.fn(() => true));
    renderPage();
    await waitFor(() => expect(screen.getByText("لغو رابطه")).toBeTruthy());
    await user.click(screen.getByText("لغو رابطه"));
    await waitFor(() => expect(mockedRel.revoke).toHaveBeenCalledWith(2));
    vi.unstubAllGlobals();
  });

  it("shows a loading state then an error with retry", async () => {
    mockedRel.list.mockRejectedValueOnce(new Error("down"));
    mockedRel.list.mockResolvedValue([]);
    renderPage();
    expect(screen.getByText("در حال بارگذاری…")).toBeTruthy();
    await waitFor(() => expect(screen.getByText("تلاش دوباره")).toBeTruthy());
    const user = userEvent.setup();
    await user.click(screen.getByText("تلاش دوباره"));
    await waitFor(() => expect(screen.getByText("هنوز رابطه‌ای نداری.")).toBeTruthy());
  });
});
