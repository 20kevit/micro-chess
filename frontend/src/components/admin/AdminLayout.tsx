import { NavLink } from "react-router-dom";
import { t } from "../../i18n";

const LINKS: Array<[string, string]> = [
  ["/admin", "admin.dashboard"],
  ["/admin/exercises", "admin.exercises"],
  ["/admin/puzzles", "admin.puzzles"],
  ["/admin/generators", "admin.generators"],
  ["/admin/review-queue", "admin.reviewQueue"],
  ["/admin/users", "admin.users"],
  ["/admin/analytics", "admin.analytics"],
  ["/admin/sales", "admin.sales"],
  ["/admin/support", "admin.support"],
  ["/admin/insights", "admin.insights"],
  ["/admin/system", "admin.system"],
  ["/admin/audit", "admin.auditLog"],
];

export function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <nav aria-label={t("admin.title")} className="mb-3 flex gap-2 overflow-x-auto pb-1">
        {LINKS.map(([to, key]) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/admin"}
            className={({ isActive }) =>
              `min-h-[44px] inline-flex shrink-0 items-center rounded-full px-4 text-sm font-bold ${
                isActive ? "bg-violet-700 text-white" : "bg-violet-100 text-violet-700"
              }`
            }
          >
            {t(key as never)}
          </NavLink>
        ))}
      </nav>
      {children}
    </div>
  );
}
