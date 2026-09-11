// Route guard: UX only. Every protected API still authorizes server-side.
import { Navigate, useLocation } from "react-router-dom";
import type { JSX } from "react";
import { t } from "../i18n";
import { useAuth } from "./auth-context";

export function RequireAuth({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (!user) return <Navigate to="/login" replace state={{ next: location.pathname }} />;
  return children;
}
