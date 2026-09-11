// Admin route guard: UX only. Every admin API still authorizes
// server-side via canonical capabilities; hiding routes never grants access.
import { Navigate, useLocation } from "react-router-dom";
import type { JSX } from "react";
import { t } from "../i18n";
import { useAuth } from "./auth-context";

export function isAdminRole(roles: string[] | undefined): boolean {
  return roles?.includes("ADMIN") ?? false;
}

export function RequireAdmin({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (!user) return <Navigate to="/login" replace state={{ next: location.pathname }} />;
  if (!isAdminRole(user.roles))
    return <p className="py-8 text-center font-bold text-stone-500">{t("admin.forbidden")}</p>;
  return children;
}
