import { useEffect, useMemo, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { t } from "../../i18n";
import type { FaKey } from "../../i18n/fa";
import { useAuth } from "../../lib/auth-context";

const GROUPS: Array<{
  label: FaKey;
  links: Array<{ to: string; label: FaKey; end?: boolean }>;
}> = [
  {
    label: "admin.nav.dashboard",
    links: [{ to: "/admin", label: "admin.nav.dashboard", end: true }],
  },
  {
    label: "admin.nav.content",
    links: [
      { to: "/admin/exercises", label: "admin.exercises" },
      { to: "/admin/puzzles", label: "admin.puzzles" },
      { to: "/admin/generators", label: "admin.generators" },
      { to: "/admin/review-queue", label: "admin.reviewQueue" },
    ],
  },
  {
    label: "admin.nav.usersGroup",
    links: [
      { to: "/admin/users", label: "admin.users" },
      { to: "/admin/support", label: "admin.support" },
    ],
  },
  {
    label: "admin.nav.reports",
    links: [
      { to: "/admin/analytics", label: "admin.analytics" },
      { to: "/admin/insights", label: "admin.insights" },
      { to: "/admin/system", label: "admin.system" },
      { to: "/admin/audit", label: "admin.auditLog" },
    ],
  },
  {
    label: "admin.nav.salesGroup",
    links: [
      { to: "/admin/sales", label: "admin.sales", end: true },
      { to: "/admin/sales?tab=plans", label: "admin.plans" },
      { to: "/admin/sales?tab=subscriptions", label: "admin.subscriptions" },
      { to: "/admin/sales?tab=coupons", label: "admin.coupons" },
      { to: "/admin/sales?tab=campaigns", label: "admin.campaigns" },
      { to: "/admin/sales?tab=payments", label: "admin.payments" },
    ],
  },
];

export function AdminLayout({ children }: { children?: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const content = children ?? <Outlet />;

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname, location.search]);

  const activeLabel = useMemo(() => {
    for (const group of GROUPS) {
      const match = [...group.links]
        .sort((left, right) => right.to.length - left.to.length)
        .find((link) => {
          const [path, query] = link.to.split("?");
          if (query) return location.pathname === path && location.search === `?${query}`;
          return link.end
            ? location.pathname === path
            : location.pathname === path || location.pathname.startsWith(`${path}/`);
        });
      if (match) return t(match.label);
    }
    return t("admin.title");
  }, [location.pathname, location.search]);

  async function onLogout() {
    await logout();
    navigate("/", { replace: true });
  }

  const sidebar = (
    <aside
      className={`fixed inset-y-0 right-0 z-50 flex h-dvh flex-col border-l border-stone-200 bg-white shadow-2xl transition-all duration-200 lg:sticky lg:top-0 lg:z-20 lg:h-dvh lg:translate-x-0 lg:shadow-none ${
        collapsed ? "lg:w-20" : "lg:w-72"
      } w-72 ${mobileOpen ? "translate-x-0" : "translate-x-full"}`}
    >
      <div className="flex min-h-20 items-center justify-between gap-2 border-b border-stone-100 px-4">
        <Link to="/admin" className="min-w-0">
          <p className="truncate text-lg font-black text-violet-800">{t("app.name")}</p>
          <p className="truncate text-xs text-stone-500">{t("admin.nav.workspace")}</p>
        </Link>
        <button
          type="button"
          onClick={() => (window.innerWidth < 1024 ? setMobileOpen(false) : setCollapsed((value) => !value))}
          className="min-h-11 min-w-11 rounded-xl border border-stone-200 px-3 text-sm font-bold text-violet-700"
          aria-label={t(mobileOpen ? "admin.nav.close" : collapsed ? "admin.nav.expand" : "admin.nav.collapse")}
        >
          {mobileOpen ? t("admin.nav.close") : collapsed ? ">" : "<"}
        </button>
      </div>
      <nav aria-label={t("admin.title")} className="flex-1 overflow-y-auto px-3 py-4">
        <div className="flex flex-col gap-5">
          {GROUPS.map((group) => (
            <div key={group.label}>
              <p
                className={`mb-2 px-3 text-xs font-black text-stone-400 ${collapsed ? "lg:hidden" : ""}`}
              >
                {t(group.label)}
              </p>
              <div className="flex flex-col gap-1">
                {group.links.map((link) => {
                  const [path, query] = link.to.split("?");
                  const active = query
                    ? location.pathname === path && location.search === `?${query}`
                    : link.end
                      ? location.pathname === path
                      : location.pathname === path || location.pathname.startsWith(`${path}/`);
                  const label = t(link.label);
                  return (
                    <NavLink
                      key={link.to}
                      to={link.to}
                      end={Boolean(link.end || query)}
                      title={collapsed ? label : undefined}
                      className={`flex min-h-11 items-center rounded-xl px-3 text-sm font-bold transition ${
                        active
                          ? "bg-violet-700 text-white shadow-sm"
                          : "text-stone-600 hover:bg-violet-50 hover:text-violet-800"
                      } ${collapsed ? "lg:justify-center lg:px-0" : ""}`}
                    >
                      <span className={collapsed ? "lg:hidden" : ""}>{label}</span>
                      <span className={`h-2 w-2 rounded-full bg-current ${collapsed ? "hidden lg:block" : "hidden"}`} />
                    </NavLink>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </nav>
    </aside>
  );

  return (
    <div dir="rtl" className="flex min-h-dvh bg-[#f6f4ff] text-stone-800">
      {mobileOpen ? (
        <button
          type="button"
          aria-label={t("admin.nav.close")}
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 z-40 bg-stone-950/40 lg:hidden"
        />
      ) : null}
      {sidebar}
      <div className="min-w-0 flex-1 lg:ml-0">
        <header className="sticky top-0 z-30 flex min-h-20 items-center justify-between gap-3 border-b border-stone-200 bg-white/95 px-4 backdrop-blur md:px-6">
          <div className="flex min-w-0 items-center gap-2">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="min-h-11 min-w-11 rounded-xl border border-stone-200 px-3 font-bold text-violet-700 lg:hidden"
              aria-label={t("admin.nav.open")}
            >
              {t("admin.nav.open")}
            </button>
            <div className="min-w-0">
              <p className="truncate text-lg font-black text-stone-900">{activeLabel}</p>
              <p className="truncate text-xs text-stone-500">{t("admin.title")}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {user ? (
              <>
                <Link
                  to="/notifications"
                  className="hidden min-h-11 items-center rounded-xl px-3 text-sm font-bold text-violet-700 sm:inline-flex"
                >
                  {t("nav.notifications")}
                </Link>
                <Link
                  to="/account"
                  className="max-w-40 truncate rounded-xl bg-violet-50 px-3 py-2 text-sm font-bold text-violet-800"
                  dir="ltr"
                >
                  {user.username}
                </Link>
                <button
                  type="button"
                  onClick={() => void onLogout()}
                  className="min-h-11 rounded-xl px-3 text-sm font-bold text-stone-500"
                >
                  {t("auth.logout")}
                </button>
              </>
            ) : null}
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1600px] p-3 md:p-6">{content}</main>
      </div>
    </div>
  );
}
