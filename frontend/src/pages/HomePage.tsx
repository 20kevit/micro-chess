import { useEffect, useState } from "react";
import { useAuth } from "../lib/auth-context";
import { t } from "../i18n";
import { activeRoleOf } from "../lib/require-admin";
import { LandingPage } from "../components/landing/LandingPage";
import { AdminDashboardPage } from "./AdminDashboardPage";
import { DashboardPage } from "./DashboardPage";
import { JourneyPage } from "./JourneyPage";
import { OnboardingPage } from "./OnboardingPage";
import { CoachStudentsPage, ParentChildrenPage } from "./MentorStudentsPage";
import { onboardingApi } from "../api/client";

// Home: role-separated landing. Anonymous visitors get the parent-focused
// marketing landing; each authenticated session lands on its own
// active-role view. PLAYER accounts flow through onboarding into the
// Daily Journey. Phone verification (Telegram/Bale) is optional for
// Free use and never gates the journey: it is offered at the daily
// limit, on the account page, and in the premium flow.
export function HomePage() {
  const { user, loading } = useAuth();
  const [onboarded, setOnboarded] = useState<boolean | null>(null);

  useEffect(() => {
    if (!user) return;
    let alive = true;
    onboardingApi
      .get()
      .then((o) => {
        if (alive) setOnboarded(o.onboarding_completed);
      })
      .catch(() => {
        if (alive) setOnboarded(true);
      });
    return () => {
      alive = false;
    };
  }, [user]);

  if (loading) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (!user) return <LandingPage />;
  const active = activeRoleOf(user) ?? user.roles[0] ?? "PLAYER";
  if (active === "ADMIN") return <AdminDashboardPage />;
  if (active === "COACH") return <CoachStudentsPage />;
  if (active === "PARENT") return <ParentChildrenPage />;
  if (onboarded === null) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (!onboarded) return <OnboardingPage />;
  return <JourneyPage />;
}

export function PlayerHomePage() {
  return <DashboardPage />;
}
