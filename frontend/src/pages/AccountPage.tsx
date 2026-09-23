import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { billingApi, quotaApi, verificationApi } from "../api/client";
import type { Quota, Subscription, VerificationStatus } from "../api/types";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import type { FaKey } from "../i18n/fa";
import { useAuth } from "../lib/auth-context";
import { authErrorKey } from "../lib/auth-errors";
import { faNum } from "../lib/playerDisplay";

// Minimal account screen: server-owned identity only. Quick links follow
// the session's active role so admin/coach/parent/player dashboards never
// mix. Multi-role accounts switch this session's active role here
// (server-authoritative). Subscription state is display-only; the backend
// owns access.
export function AccountPage() {
  const { user, logout, switchRole } = useAuth();
  const navigate = useNavigate();
  const [switching, setSwitching] = useState(false);
  const [switchError, setSwitchError] = useState<FaKey | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [quota, setQuota] = useState<Quota | null>(null);
  const [verification, setVerification] = useState<VerificationStatus | null>(null);

  useEffect(() => {
    let alive = true;
    if (user) {
      billingApi
        .subscription()
        .then((s) => {
          if (alive) setSubscription(s);
        })
        .catch(() => {});
      quotaApi
        .get()
        .then((q) => {
          if (alive) setQuota(q);
        })
        .catch(() => {});
      verificationApi
        .status()
        .then((v) => {
          if (alive) setVerification(v);
        })
        .catch(() => {});
    }
    return () => {
      alive = false;
    };
  }, [user]);
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
          <div className="rounded-2xl bg-violet-50 px-4 py-3 text-center">
            <p className="text-sm font-bold text-stone-700">
              {t("account.plan")}:{" "}
              {subscription
                ? subscription.plan_code === "premium"
                  ? `${t("account.plan.premium")} ✓`
                  : t("account.plan.free")
                : t("common.loading")}
              {subscription ? ` (${t(`pricing.status.${subscription.status}` as FaKey)})` : null}
            </p>
            {quota ? (
              <p className="mt-1 text-sm font-bold text-stone-700">
                {t("account.todayUsage")}: {faNum(quota.used)} {t("account.of")} {faNum(quota.limit)}
              </p>
            ) : null}
            {subscription && subscription.plan_code === "free" ? (
              <p className="mt-1 text-xs text-stone-500">{t("account.freeNote")}</p>
            ) : null}
            {verification ? (
              <p className="mt-1 text-sm font-bold text-stone-700">
                {t("account.phone")}:{" "}
                {verification.verified
                  ? `${t("account.verified")} ✓`
                  : t("account.unverified")}
              </p>
            ) : null}
            {verification && verification.verified && verification.channel ? (
              <p className="mt-1 text-xs text-stone-500">
                {t("account.verifyChannel")}:{" "}
                {verification.channel === "telegram" ? t("verify.telegram") : t("verify.bale")}
              </p>
            ) : null}
            <Link to="/pricing" className="mt-2 block">
              <Button variant="secondary" className="w-full">
                {t("account.viewPricing")}
              </Button>
            </Link>
            {subscription && subscription.plan_code === "free" ? (
              <Link to="/premium" className="mt-2 block">
                <Button className="w-full">{t("premium.cta")}</Button>
              </Link>
            ) : null}
            {verification && !verification.verified ? (
              <Link to="/verify" className="mt-2 block">
                <Button variant="secondary" className="w-full">
                  {t("account.verifyCta")}
                </Button>
              </Link>
            ) : null}
          </div>
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
