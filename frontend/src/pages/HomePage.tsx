import { useEffect, useState } from "react";
import { useAuth } from "../lib/auth-context";
import { t } from "../i18n";
import { activeRoleOf } from "../lib/require-admin";
import { LandingPage } from "../components/landing/LandingPage";
import { AdminDashboardPage } from "./AdminDashboardPage";
import { DashboardPage } from "./DashboardPage";
import { JourneyPage } from "./JourneyPage";
import { OnboardingPage } from "./OnboardingPage";
import { VerifyPhonePage } from "./VerifyPhonePage";
import { CoachStudentsPage, ParentChildrenPage } from "./MentorStudentsPage";
import { onboardingApi, phoneApi } from "../api/client";

// Home: role-separated landing. Anonymous visitors get the parent-focused
// marketing landing; each authenticated session lands on its own
// active-role view. PLAYER accounts flow through the P11 journey gate:
// phone verification -> onboarding -> Daily Journey (never a dead-end
// generic dashboard).
export function HomePage() {
  const { user, loading } = useAuth();
  const [gate, setGate] = useState<"loading" | "phone" | "onboarding" | "journey">("loading");

  useEffect(() => {
    if (!user) return;
    let alive = true;
    Promise.all([phoneApi.status().catch(() => null), onboardingApi.get().catch(() => null)]).then(
      ([phone, onboarding]) => {
        if (!alive) return;
        if (phone && !phone.verified) setGate("phone");
        else if (onboarding && !onboarding.onboarding_completed) setGate("onboarding");
        else setGate("journey");
      },
    );
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
  if (gate === "loading") return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (gate === "phone") return <VerifyPhonePage />;
  if (gate === "onboarding") return <OnboardingPage />;
  return <JourneyPage />;
}

export function PlayerHomePage() {
  return <DashboardPage />;
}
