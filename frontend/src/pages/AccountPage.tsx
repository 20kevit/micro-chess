import { Link, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import type { FaKey } from "../i18n/fa";
import { useAuth } from "../lib/auth-context";

// Minimal account screen: server-owned identity only. No profile
// dashboard, ratings, or analytics (later phases).
export function AccountPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;

  async function onLogout() {
    await logout();
    navigate("/", { replace: true });
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
        <div className="mt-4 flex flex-col gap-2">
          <Link to="/profile" className="block">
            <Button variant="secondary" className="w-full">
              {t("auth.goToProfile")}
            </Button>
          </Link>
          <Link to="/exercises" className="block">
            <Button variant="secondary" className="w-full">
              {t("auth.backToExercises")}
            </Button>
          </Link>
          <Button variant="ghost" onClick={onLogout}>
            {t("auth.logout")}
          </Button>
        </div>
      </Card>
    </div>
  );
}
