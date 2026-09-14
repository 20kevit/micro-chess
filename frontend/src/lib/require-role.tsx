// Role route guard: UX only. Every protected API still authorizes
// server-side via canonical capabilities; hiding routes never grants access.
// The guard follows the session's active role (not the assigned set).
import { Navigate, useLocation } from "react-router-dom";
import type { JSX } from "react";
import { t } from "../i18n";
import { useAuth } from "./auth-context";
import { activeRoleOf } from "./require-admin";

export function RequireRole({ allowed, children }: { allowed: string[]; children: JSX.Element }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (!user) return <Navigate to="/login" replace state={{ next: location.pathname }} />;
  const active = activeRoleOf(user) ?? user.roles[0] ?? null;
  if (!active || !allowed.includes(active))
    return <p className="py-8 text-center font-bold text-stone-500">{t("admin.forbidden")}</p>;
  return children;
}
