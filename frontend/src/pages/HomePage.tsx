import { useAuth } from "../lib/auth-context";
import { t } from "../i18n";
import { activeRoleOf } from "../lib/require-admin";
import { AdminDashboardPage } from "./AdminDashboardPage";
import { DashboardPage } from "./DashboardPage";
import { ExercisesPage } from "./ExercisesPage";
import { CoachStudentsPage, ParentChildrenPage } from "./MentorStudentsPage";

// Home: role-separated landing. Anonymous visitors get the exercise menu;
// each authenticated session lands on its own active-role dashboard so
// player/coach/parent/admin views never mix.
export function HomePage() {
  const { user, loading } = useAuth();
  if (loading) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (!user) return <ExercisesPage />;
  const active = activeRoleOf(user) ?? user.roles[0] ?? "PLAYER";
  if (active === "ADMIN") return <AdminDashboardPage />;
  if (active === "COACH") return <CoachStudentsPage />;
  if (active === "PARENT") return <ParentChildrenPage />;
  return <DashboardPage />;
}
