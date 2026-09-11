import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { t } from "../../i18n";
import { useAuth } from "../../lib/auth-context";
import { isAdminRole } from "../../lib/require-admin";

// Mobile-first shell: content + bottom nav on phones, top bar on desktop.
export function AppShell() {
  const { user, loading, logout } = useAuth();
  const navigate = useNavigate();
  const link = ({ isActive }: { isActive: boolean }) =>
    `flex min-h-[44px] flex-1 items-center justify-center rounded-2xl text-base font-bold ${
      isActive ? "bg-violet-600 text-white" : "text-violet-700"
    }`;

  async function onLogout() {
    await logout();
    navigate("/", { replace: true });
  }

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-3xl flex-col bg-[#f6f4ff]">
      <header className="flex items-center justify-between gap-2 px-4 pt-4">
        <span className="text-xl font-black text-violet-700">{t("app.name")}</span>
        <div className="flex items-center gap-2">
          {loading ? null : user ? (
            <>
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
        <NavLink to="/exercises" className={link}>
          {t("nav.exercises")}
        </NavLink>
        {user ? (
          <>
            <NavLink to="/progress" className={link}>
              {t("nav.progress")}
            </NavLink>
            <NavLink to="/profile" className={link}>
              {t("nav.profile")}
            </NavLink>
            {isAdminRole(user.roles) ? (
              <NavLink to="/admin" className={link}>
                {t("nav.admin")}
              </NavLink>
            ) : null}
          </>
        ) : null}
      </nav>
    </div>
  );
}
