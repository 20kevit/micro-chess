import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import type { FaKey } from "../i18n/fa";
import { useAuth } from "../lib/auth-context";
import { authErrorKey } from "../lib/auth-errors";

// Minimal account screen: server-owned identity only. Quick links follow
// the session's active role so admin/coach/parent/player dashboards never
// mix. Multi-role accounts switch this session's active role here
// (server-authoritative).
export function AccountPage() {
  const { user, logout, switchRole } = useAuth();
  const navigate = useNavigate();
  const [switching, setSwitching] = useState(false);
  const [switchError, setSwitchError] = useState<FaKey | null>(null);
  if (!user) return null;

  async function onLogout() {
    await logout();
    navigate("/", { replace: true });
  }

  const activeRole =
    user.active_role && user.roles.includes(user.active_role)
      ? user.active_role
      : (user.roles[0] ?? "PLAYER");
  const otherRoles = user.roles.filter((role) => role !== activeRole);

  async function onSwitch(role: string) {
    setSwitching(true);
    setSwitchError(null);
    try {
      await switchRole(role);
    } catch (err) {
      setSwitchError(authErrorKey(err));
    } finally {
      setSwitching(false);
    }
  }

  return (
    <div>
      <PageHeader title={t("auth.accountTitle")} subtitle={t("auth.accountSubtitle")} />
      <Card>
        <p dir="ltr" className="text-center text-2xl font-black text-stone-900">
          {user.username}
        </p>
        <p className="mt-2 text-center text-sm text-stone-500">
          {t("auth.roles")}:{" "}
          {user.roles
            .map((role) => t(`auth.role.${role}` as FaKey))
            .join("، ")}
        </p>
        {otherRoles.length > 0 ? (
          <div className="mt-3 rounded-2xl bg-violet-50 px-4 py-3">
            <p className="text-center text-sm font-bold text-stone-700">
              {t("auth.currentRole")}: {t(`auth.role.${activeRole}` as FaKey)}
            </p>
            <p className="mt-1 text-center text-sm text-stone-500">{t("auth.switchRole")}</p>
            <div className="mt-2 flex flex-col gap-2">
              {otherRoles.map((role) => (
                <Button
                  key={role}
                  variant="secondary"
                  disabled={switching}
                  onClick={() => void onSwitch(role)}
                >
                  {t(`auth.role.${role}` as FaKey)}
                </Button>
              ))}
            </div>
            {switchError ? (
              <p role="alert" className="mt-2 rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-600">
                {t(switchError)}
              </p>
            ) : null}
          </div>
        ) : null}
        <div className="mt-4 flex flex-col gap-2">
          {activeRole === "ADMIN" ? (
            <Link to="/admin" className="block">
              <Button variant="secondary" className="w-full">
                {t("nav.admin")}
              </Button>
            </Link>
          ) : null}
          {activeRole === "COACH" ? (
            <>
              <Link to="/coach/students" className="block">
                <Button variant="secondary" className="w-full">
                  {t("nav.coach")}
                </Button>
              </Link>
              <Link to="/exercises" className="block">
                <Button variant="secondary" className="w-full">
                  {t("auth.backToExercises")}
                </Button>
              </Link>
            </>
          ) : null}
          {activeRole === "PARENT" ? (
            <Link to="/parent/children" className="block">
              <Button variant="secondary" className="w-full">
                {t("nav.parent")}
              </Button>
            </Link>
          ) : null}
          {activeRole === "PLAYER" ? (
            <>
              <Link to="/profile" className="block">
                <Button variant="secondary" className="w-full">
                  {t("auth.goToProfile")}
                </Button>
              </Link>
              <Link to="/progress" className="block">
                <Button variant="secondary" className="w-full">
                  {t("nav.progress")}
                </Button>
              </Link>
              <Link to="/exercises" className="block">
                <Button variant="secondary" className="w-full">
                  {t("auth.backToExercises")}
                </Button>
              </Link>
            </>
          ) : null}
          <Button variant="ghost" onClick={onLogout}>
            {t("auth.logout")}
          </Button>
        </div>
      </Card>
    </div>
  );
}
