import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { notificationsApi } from "../../api/client";
import { t } from "../../i18n";
import { useAuth } from "../../lib/auth-context";
import { activeRoleOf } from "../../lib/require-admin";
import { faNum } from "../../lib/playerDisplay";

// Mobile-first shell: content + bottom nav on phones, top bar on desktop.
export function AppShell() {
  const { user, loading, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [unread, setUnread] = useState(0);
  const link = ({ isActive }: { isActive: boolean }) =>
    `flex min-h-[44px] flex-1 items-center justify-center rounded-2xl text-base font-bold ${
      isActive ? "bg-violet-600 text-white" : "text-violet-700"
    }`;

  // Unread badge refreshes on navigation (no polling); the server owns
  // the count and failures simply hide the badge.
  useEffect(() => {
    if (!user) {
      setUnread(0);
      return;
    }
    let alive = true;
    notificationsApi
      .unreadCount()
      .then((r) => {
        if (alive) setUnread(r.unread_count);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [user, location.pathname]);

  async function onLogout() {
    await logout();
    navigate("/", { replace: true });
  }

  // Role-separated navigation: each session sees only its own active-role
  // tabs. Backend capabilities stay authoritative; this is UX only.
  // PLAYER: play + own progress. COACH: students + exercises. PARENT:
  // children. ADMIN: management only (no player tabs).
  const active = user ? (activeRoleOf(user) ?? user.roles[0] ?? null) : null;
  const isPlayer = active === "PLAYER";
  const isCoach = active === "COACH";
  const isParent = active === "PARENT";
  const isAdmin = active === "ADMIN";

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-3xl flex-col bg-[#f6f4ff]">
      <header className="flex items-center justify-between gap-2 px-4 pt-4">
        <span className="text-xl font-black text-violet-700">{t("app.name")}</span>
        <div className="flex flex-wrap items-center justify-end gap-2">
          {loading ? null : user ? (
            <>
              <Link
                to="/notifications"
                aria-label={t("nav.notifications")}
                className="flex min-h-[44px] items-center gap-1 rounded-2xl px-3 text-sm font-bold text-violet-700"
              >
                {t("nav.notifications")}
                {unread > 0 ? (
                  <span className="flex min-h-[24px] min-w-[24px] items-center justify-center rounded-full bg-red-500 px-1 text-xs font-black text-white">
                    {faNum(unread)}
                  </span>
                ) : null}
              </Link>
              <Link
                to="/support"
                className="flex min-h-[44px] items-center rounded-2xl px-3 text-sm font-bold text-violet-700"
              >
                {t("nav.support")}
              </Link>
              <Link
                to="/account"
                className="flex min-h-[44px] items-center rounded-2xl px-3 text-sm font-bold text-violet-700"
              >
                <span dir="ltr">{user.username}</span>
              </Link>
              <button
                type="button"
                onClick={onLogout}
                className="flex min-h-[44px] items-center rounded-2xl px-3 text-sm font-bold text-stone-500"
              >
                {t("auth.logout")}
              </button>
            </>
          ) : (
            <>
              <Link
                to="/login"
                className="flex min-h-[44px] items-center rounded-2xl px-3 text-sm font-bold text-violet-700"
              >
                {t("nav.login")}
              </Link>
              <Link
                to="/register"
                className="flex min-h-[44px] items-center rounded-2xl bg-violet-600 px-3 text-sm font-bold text-white"
              >
                {t("nav.register")}
              </Link>
            </>
          )}
        </div>
      </header>
      <main className="flex-1 px-4 pb-24 pt-4 md:pb-8">
        <Outlet />
      </main>
      <nav className="fixed inset-x-0 bottom-0 mx-auto flex w-full max-w-3xl gap-2 bg-white/90 p-3 backdrop-blur md:static md:bg-transparent">
        <NavLink to="/" className={link} end>
          {t("nav.home")}
        </NavLink>
        {user ? (
          <>
            {isPlayer || isCoach ? (
              <NavLink to="/exercises" className={link}>
                {t("nav.exercises")}
              </NavLink>
            ) : null}
            {isPlayer ? (
              <>
                <NavLink to="/progress" className={link}>
                  {t("nav.progress")}
                </NavLink>
                <NavLink to="/profile" className={link}>
                  {t("nav.profile")}
                </NavLink>
                <NavLink to="/relationships" className={link}>
                  {t("nav.relationships")}
                </NavLink>
              </>
            ) : null}
            {isCoach ? (
              <>
                <NavLink to="/coach/students" className={link}>
                  {t("nav.coach")}
                </NavLink>
                <NavLink to="/relationships" className={link}>
                  {t("nav.relationships")}
                </NavLink>
              </>
            ) : null}
            {isParent ? (
              <>
                <NavLink to="/parent/children" className={link}>
                  {t("nav.parent")}
                </NavLink>
                <NavLink to="/relationships" className={link}>
                  {t("nav.relationships")}
                </NavLink>
              </>
            ) : null}
            {isAdmin ? (
              <NavLink to="/admin" className={link}>
                {t("nav.admin")}
              </NavLink>
            ) : null}
          </>
        ) : (
          <NavLink to="/exercises" className={link}>
            {t("nav.exercises")}
          </NavLink>
        )}
      </nav>
    </div>
  );
}
