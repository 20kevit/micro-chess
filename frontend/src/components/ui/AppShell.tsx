import { NavLink, Outlet } from "react-router-dom";
import { t } from "../../i18n";

// Mobile-first shell: content + bottom nav on phones, top bar on desktop.
export function AppShell() {
  const link = ({ isActive }: { isActive: boolean }) =>
    `flex min-h-[44px] flex-1 items-center justify-center rounded-2xl text-base font-bold ${
      isActive ? "bg-violet-600 text-white" : "text-violet-700"
    }`;

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-3xl flex-col bg-[#f6f4ff]">
      <header className="flex items-center justify-between px-4 pt-4">
        <span className="text-xl font-black text-violet-700">{t("app.name")}</span>
        <span className="text-xs text-stone-500">{t("app.tagline")}</span>
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
      </nav>
    </div>
  );
}
