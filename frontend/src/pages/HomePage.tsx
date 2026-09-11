import { useAuth } from "../lib/auth-context";
import { DashboardPage } from "./DashboardPage";
import { ExercisesPage } from "./ExercisesPage";

// Home: authenticated players get their dashboard, anonymous visitors get
// the exercise menu (unchanged public experience).
export function HomePage() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <ExercisesPage />;
  return <DashboardPage />;
}
