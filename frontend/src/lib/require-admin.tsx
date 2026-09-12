// Admin route guard: UX only. Every admin API still authorizes
// server-side via canonical capabilities; hiding routes never grants access.
// The guard follows the session's active role (not the assigned set): a
// multi-role user in a PLAYER session sees the forbidden notice, exactly
// like the backend answers 403 for that session.
import { Navigate, useLocation } from "react-router-dom";
import type { JSX } from "react";
import { t } from "../i18n";
import { useAuth } from "./auth-context";

export function activeRoleOf(user: { roles: string[]; active_role?: string } | null): string | null {
  if (!user) return null;
  if (user.active_role && user.roles.includes(user.active_role)) return user.active_role;
  return null;
}

export function hasRole(
  roles: string[] | undefined,
  role: string,
  activeRole?: string | null,
): boolean {
  if (activeRole) return activeRole === role;
  return roles?.includes(role) ?? false;
}

export function isAdminRole(roles: string[] | undefined, activeRole?: string | null): boolean {
  return hasRole(roles, "ADMIN", activeRole);
}

export function RequireAdmin({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (!user) return <Navigate to="/login" replace state={{ next: location.pathname }} />;
  if (!isAdminRole(user.roles, activeRoleOf(user)))
    return <p className="py-8 text-center font-bold text-stone-500">{t("admin.forbidden")}</p>;
  return children;
}
