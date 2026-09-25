import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { adminApi, apiCode } from "../api/client";
import type { UserProfileFull } from "../api/types";
import type { FaKey } from "../i18n/fa";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import {
  adminSourceLabel,
  adminStatusLabel,
  faDate,
  faDateTime,
  faNum,
  exerciseTitle,
  verificationChannelLabel,
} from "../lib/playerDisplay";

type Tab = "overview" | "learning" | "commercial" | "timeline";
type UserTab = [Tab, FaKey];

const TABS: UserTab[] = [
  ["overview", "admin.overviewTab"],
  ["learning", "admin.learningTab"],
  ["commercial", "admin.commercialTab"],
  ["timeline", "admin.timelineTab"],
];
const MANAGEABLE_ROLES = ["COACH", "PARENT", "ADMIN"] as const;
const ROLE_KEYS: Record<string, FaKey> = {
  PLAYER: "auth.role.PLAYER",
  COACH: "auth.role.COACH",
  PARENT: "auth.role.PARENT",
  ADMIN: "auth.role.ADMIN",
};

function roleLabel(role: string): string {
  return t(ROLE_KEYS[role] ?? "admin.unknown");
}

function confidenceLabel(value: string): string {
  if (value === "high") return t("admin.status.high");
  if (value === "medium") return t("admin.status.medium");
  if (value === "low") return t("admin.confidence.low");
  return t("admin.unknown");
}

function learningLevelLabel(value: string): string {
  if (value === "beginner") return t("onboarding.experience.beginner");
  if (value === "advanced") return t("onboarding.experience.advanced");
  if (value === "mastered" || value === "proficient") return t("admin.user.mastery");
  if (value === "emerging" || value === "developing" || value === "struggling") return t("admin.user.learning");
  if (value === "unseen") return t("admin.empty");
  return t("admin.unknown");
}

function eventLabel(kind: string): string {
  if (kind === "first_attempt") return t("admin.eventFirstAttempt");
  if (kind === "subscription") return t("admin.eventSubscription");
  if (kind === "payment") return t("admin.eventPayment");
  if (kind === "coupon") return t("admin.eventCoupon");
  if (kind === "recommendation") return t("admin.eventRecommendation");
  if (kind === "support") return t("admin.eventSupport");
  if (kind === "registered") return t("admin.eventRegistered");
  return t("admin.unknown");
}

function redemptionStatusLabel(status: string): string {
  if (status === "applied") return t("admin.status.verified");
  if (status === "rejected") return t("admin.status.rejected");
  if (status === "pending") return t("admin.status.pending");
  return adminStatusLabel(status);
}

function subscriptionStatusLabel(status: string): string {
  if (status === "suspended") return t("admin.statusSuspended");
  return adminStatusLabel(status);
}

function paymentProviderLabel(provider: string): string {
  return provider && provider !== "none" ? t("admin.providerLabel") : t("admin.health.notConnected");
}

function planLabel(plan: string | null): string {
  if (plan === "free") return t("account.plan.free");
  if (plan === "premium") return t("account.plan.premium");
  return plan ? t("admin.unknown") : t("admin.noSubscription");
}

function timelineDetail(kind: string, detail: string): ReactNode {
  if (kind === "subscription") {
    const match = detail.match(/^(.*?)->(.*?)(?: \((.*)\))?$/);
    if (match) {
      return <span dir="ltr">{subscriptionStatusLabel(match[1])} → {subscriptionStatusLabel(match[2])}{match[3] ? ` (${t("admin.details")})` : ""}</span>;
    }
  }
  if (["payment", "coupon", "recommendation", "support"].includes(kind)) {
    const parts = detail.split(" ");
    const status = parts[parts.length - 1];
    if (["open", "pending", "trialing", "active", "expired", "cancelled", "past_due", "requires_action", "revoked", "verified", "failed", "answered", "closed", "applied", "shown", "accepted", "skipped", "completed", "abandoned"].includes(status)) {
      return <span dir="ltr">{parts.slice(0, -1).join(" ")} {subscriptionStatusLabel(status)}</span>;
    }
  }
  return <span>{t("admin.details")}</span>;
}

function dateOrDash(value: string | null | undefined): ReactNode {
  return value ? <span dir="ltr">{faDate(value)}</span> : t("admin.notAvailable");
}

function dateTimeOrDash(value: string | null | undefined): ReactNode {
  return value ? <span dir="ltr">{faDateTime(value)}</span> : t("admin.notAvailable");
}

export function AdminUserDetailPage() {
  const { id } = useParams();
  const [tab, setTab] = useState<Tab>("overview");
  const [profile, setProfile] = useState<UserProfileFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setFailed(false);
    try {
      const result = await adminApi.userProfile(Number(id));
      setProfile(result);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function runAction(action: () => Promise<unknown>, successMessage: string) {
    setBusy(true);
    setNotice("");
    try {
      await action();
      await load();
      setNotice(successMessage);
    } catch (error) {
      const code = apiCode(error);
      setNotice(code === "LAST_ADMIN" || code === "last_admin" ? t("admin.lastAdminBlocked") : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function toggleSuspension() {
    if (!profile) return;
    if (profile.overview.is_active) {
      if (!window.confirm(t("admin.suspendConfirm"))) return;
      await runAction(() => adminApi.suspendUser(profile.overview.id), t("admin.statusSuspended"));
    } else {
      if (!window.confirm(t("admin.reactivateConfirm"))) return;
      await runAction(() => adminApi.reactivateUser(profile.overview.id), t("admin.statusActive"));
    }
  }

  async function assignRole(role: string) {
    if (!profile) return;
    await runAction(() => adminApi.assignRole(profile.overview.id, role), t("admin.saveChanges"));
  }

  async function revokeRole(role: string) {
    if (!profile) return;
    await runAction(() => adminApi.revokeRole(profile.overview.id, role), t("admin.saveChanges"));
  }

  if (loading) {
    return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  }

  if (failed || !profile) {
    return (
      <div className="py-8 text-center">
        <p className="text-stone-500">{t("common.error")}</p>
        <div className="mx-auto mt-3 max-w-xs">
          <Button onClick={() => void load()} className="w-full">{t("common.retry")}</Button>
        </div>
      </div>
    );
  }

  const verification = profile.verification ?? profile.overview.verification;
  const verificationChannel = verification?.channel ?? profile.overview.verification_channel;
  const maskedPhone = verification?.phone_masked ?? profile.overview.phone_masked;
  const learning = profile.learning;
  const commercial = profile.commercial;
  const current = commercial.current_subscription;
  const subscriptions = commercial.subscriptions ?? [];
  const redemptions = commercial.redemptions ?? [];
  const payments = commercial.payments ?? [];
  const timeline = profile.timeline ?? [];

  return (
    <div>
      <PageHeader title={t("admin.usersDetail")} subtitle={t("admin.users.summary")} />
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <Link to="/admin/users" className="text-sm font-bold text-violet-700">{t("common.back")}</Link>
            <h2 className="mt-2 break-words text-2xl font-black" dir="ltr">{profile.overview.username}</h2>
            <p className="mt-1 text-stone-500">{profile.overview.display_name}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {profile.overview.roles.map((role) => <Badge key={role}>{roleLabel(role)}</Badge>)}
            </div>
          </div>
          <div className="text-left">
            <Badge>{profile.overview.is_active ? t("admin.statusActive") : t("admin.statusSuspended")}</Badge>
            <p className="mt-2 text-xs text-stone-500">{t("admin.accountState")}</p>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
          <div className="rounded-2xl bg-stone-50 p-3">
            <p className="text-xs text-stone-500">{t("admin.registered")}</p>
            <p className="mt-1 font-bold" dir="ltr">{faDateTime(profile.overview.created_at)}</p>
          </div>
          <div className="rounded-2xl bg-stone-50 p-3">
            <p className="text-xs text-stone-500">{t("admin.lastActive")}</p>
            <p className="mt-1 font-bold" dir="ltr">{faDateTime(profile.overview.last_active_at)}</p>
          </div>
           <div className="rounded-2xl bg-stone-50 p-3">
             <p className="text-xs text-stone-500">{t("admin.attempts")}</p>
             <p className="mt-1 text-lg font-black text-violet-700">{faNum(profile.overview.attempts_total)}</p>
           </div>
           <div className="rounded-2xl bg-stone-50 p-3">
             <p className="text-xs text-stone-500">{t("admin.label.plan")}</p>
             <p className="mt-1 text-lg font-black text-violet-700">{planLabel(current?.plan_code ?? null)}</p>
             <p className="mt-1 text-xs text-stone-500">{current ? subscriptionStatusLabel(current.status) : t("admin.noSubscription")}</p>
           </div>
           <div className="rounded-2xl bg-stone-50 p-3">
            <p className="text-xs text-stone-500">{t("admin.users.verification")}</p>
            <p className="mt-1 font-bold">
              {profile.overview.phone_verified ? t("account.verified") : t("account.unverified")}
            </p>
            <p className="mt-1 text-xs text-stone-500">{t("account.verifyChannel")}: {verificationChannelLabel(verificationChannel)}</p>
            <p className="mt-1 text-xs text-stone-500" dir="ltr">{t("account.phone")}: {maskedPhone || t("admin.notAvailable")}</p>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button disabled={busy} onClick={() => void toggleSuspension()}>
            {profile.overview.is_active ? t("admin.suspend") : t("admin.reactivate")}
          </Button>
        </div>
        <div className="mt-4 border-t border-stone-100 pt-3">
          <p className="text-sm font-black">{t("admin.users.roleChange")}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {MANAGEABLE_ROLES.map((role) => {
              const assigned = profile.overview.roles.includes(role);
              return (
                <Button
                  key={role}
                  variant="secondary"
                  disabled={busy}
                  onClick={() => void (assigned ? revokeRole(role) : assignRole(role))}
                >
                  {assigned ? t("admin.revokeRole") : t("admin.assignRole")}: {roleLabel(role)}
                </Button>
              );
            })}
          </div>
        </div>
      </Card>
      {notice ? <p className="mt-2 text-center text-sm font-bold text-violet-700">{notice}</p> : null}
      <div className="my-3 flex gap-2 overflow-x-auto pb-1">
        {TABS.map(([value, key]) => (
          <button
            key={value}
            type="button"
            onClick={() => setTab(value)}
            title={value === "timeline" ? t("admin.users.activity") : undefined}
            className={`min-h-[44px] shrink-0 rounded-full px-4 text-sm font-bold ${tab === value ? "bg-violet-700 text-white" : "bg-violet-100 text-violet-700"}`}
          >
            {t(key)}
          </button>
        ))}
      </div>
      {tab === "overview" ? (
        <div className="flex flex-col gap-3">
          <Card>
            <h2 className="font-black">{t("admin.overviewTab")}</h2>
            <p className="mt-2 text-sm text-stone-600">{t("admin.user.recentOnly")}</p>
            <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3">
              <div className="rounded-2xl bg-stone-50 p-3">
                <p className="text-xs text-stone-500">{t("admin.level")}</p>
                <p className="mt-1 font-black">{learningLevelLabel(learning.overall_level)}</p>
              </div>
              <div className="rounded-2xl bg-stone-50 p-3">
                <p className="text-xs text-stone-500">{t("admin.totalXp")}</p>
                <p className="mt-1 font-black">{faNum(learning.xp?.total ?? 0)}</p>
              </div>
              <div className="rounded-2xl bg-stone-50 p-3">
                <p className="text-xs text-stone-500">{t("admin.currentStreak")}</p>
                <p className="mt-1 font-black">{faNum(learning.streak?.current ?? 0)}</p>
              </div>
            </div>
          </Card>
          <Card>
            <h2 className="font-black">{t("admin.commercialTab")}</h2>
            {current ? (
              <div className="mt-2 rounded-2xl bg-violet-50 p-3 text-sm">
                <p className="font-black" dir="ltr">{planLabel(current.plan_code)}</p>
                <p className="mt-1">{subscriptionStatusLabel(current.status)} · {adminSourceLabel(current.source)}</p>
                <p className="mt-1 text-xs text-stone-500">
                  {t("admin.label.end")}: {dateOrDash(current.current_period_end)} · {t("admin.trialDays")}: {dateOrDash(current.trial_ends_at)} · {t("admin.couponCode")}: {current.coupon_code ?? t("admin.notAvailable")}
                </p>
              </div>
            ) : <p className="mt-2 text-sm text-stone-500">{t("admin.noSubscription")}</p>}
          </Card>
        </div>
      ) : null}
      {tab === "learning" ? (
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <Card><p className="text-xs text-stone-500">{t("admin.level")}</p><p className="mt-1 text-xl font-black">{learningLevelLabel(learning.overall_level)}</p></Card>
            <Card><p className="text-xs text-stone-500">{t("admin.totalXp")}</p><p className="mt-1 text-xl font-black">{faNum(learning.xp?.total ?? 0)}</p></Card>
            <Card><p className="text-xs text-stone-500">{t("admin.currentStreak")}</p><p className="mt-1 text-xl font-black">{faNum(learning.streak?.current ?? 0)}</p></Card>
            <Card><p className="text-xs text-stone-500">{t("admin.longestStreak")}</p><p className="mt-1 text-xl font-black">{faNum(learning.streak?.longest ?? 0)}</p></Card>
          </div>
          <Card>
            <h2 className="font-black">{t("admin.skillsSeen")}</h2>
            {learning.skills.length === 0 ? <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p> : (
              <div className="mt-2 overflow-x-auto">
                <table className="w-full min-w-[520px] text-right text-sm">
                  <thead className="text-xs text-stone-500"><tr><th className="p-2">{t("admin.user.learning")}</th><th className="p-2">{t("admin.level")}</th><th className="p-2">{t("admin.label.status")}</th><th className="p-2">{t("admin.attempts")}</th></tr></thead>
                  <tbody>
                    {learning.skills.map((skill) => <tr key={skill.skill} className="border-t border-stone-100"><td className="p-2 font-bold" dir="ltr">{skill.skill}</td><td className="p-2">{learningLevelLabel(skill.level)}</td><td className="p-2">{confidenceLabel(skill.confidence)}</td><td className="p-2">{faNum(skill.evidence_count)}</td></tr>)}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
          <Card>
            <h2 className="font-black">{t("admin.exerciseUsage")}</h2>
            {learning.attempts_by_exercise.length === 0 ? <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p> : (
              <ul className="mt-2 flex flex-col gap-2">
                {learning.attempts_by_exercise.map((row) => (
                  <li key={row.exercise_slug} className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3">
                    <Link to={`/admin/exercises/${row.exercise_slug}`} className="font-bold text-violet-700">{exerciseTitle(row.exercise_slug)}</Link>
                    <span className="text-sm text-stone-500">{faNum(row.attempts)} · {faNum(row.correct)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card>
            <h2 className="font-black">{t("admin.user.mastery")}</h2>
            {learning.mastery.length === 0 ? <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p> : (
              <ul className="mt-2 flex flex-col gap-1">
                {learning.mastery.map((row) => <li key={row.skill} className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3 text-sm"><span dir="ltr" className="font-bold">{row.skill}</span><span>{adminStatusLabel(row.status)} · {confidenceLabel(row.confidence)} · {faNum(row.attempts)}</span></li>)}
              </ul>
            )}
          </Card>
        </div>
      ) : null}
      {tab === "commercial" ? (
        <div className="flex flex-col gap-3">
          <Card>
            <h2 className="font-black">{t("admin.subscriptions")}</h2>
            {current ? <p className="mt-2 text-sm"><span className="font-bold">{planLabel(current.plan_code)}</span> · {subscriptionStatusLabel(current.status)} · {adminSourceLabel(current.source)}</p> : <p className="mt-2 text-sm text-stone-500">{t("admin.noSubscription")}</p>}
            <p className="mt-2 text-xs text-stone-500">{t("admin.subscription.why")}</p>
          </Card>
          <Card>
            <h2 className="font-black">{t("admin.user.history")}</h2>
            {subscriptions.length === 0 ? <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p> : (
              <ul className="mt-2 flex flex-col gap-2">
                {subscriptions.map((subscription) => <li key={subscription.id} className="rounded-xl bg-stone-50 px-3 py-2 text-sm"><span className="font-bold">#{faNum(subscription.id)} {planLabel(subscription.plan_code)}</span><p className="mt-1 text-xs text-stone-500">{subscriptionStatusLabel(subscription.status)} · {adminSourceLabel(subscription.source)} · {dateOrDash(subscription.created_at)}</p></li>)}
              </ul>
            )}
          </Card>
          <Card>
            <h2 className="font-black">{t("admin.user.attribution")}</h2>
            {!commercial.attribution ? <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p> : (
              <div className="mt-2 grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
                <p>{t("admin.sourceLabel")}: {adminSourceLabel(commercial.attribution.first_source)}</p>
                <p>{t("admin.label.campaign")}: <span dir="ltr">{commercial.attribution.first_campaign || t("admin.notAvailable")}</span></p>
                <p>{t("admin.couponCode")}: <span dir="ltr">{commercial.attribution.first_coupon_code || t("admin.notAvailable")}</span></p>
                <p>{t("admin.createdAt")}: {dateTimeOrDash(commercial.attribution.first_touched_at)}</p>
                <p>{t("admin.sourceLabel")}: {adminSourceLabel(commercial.attribution.last_source)}</p>
              </div>
            )}
          </Card>
          <Card>
            <h2 className="font-black">{t("admin.coupons")}</h2>
            {redemptions.length === 0 ? <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p> : (
              <ul className="mt-2 flex flex-col gap-2">{redemptions.map((redemption, index) => <li key={`${redemption.code}-${index}`} className="rounded-xl bg-stone-50 px-3 py-2 text-sm"><span className="font-bold" dir="ltr">{redemption.code}</span><p className="mt-1 text-xs text-stone-500">{redemptionStatusLabel(redemption.status)} · {t("admin.discountValue")}: {faNum(redemption.discount_granted_minor)} · {t("admin.trialDays")}: {faNum(redemption.trial_days_granted)}</p><p className="mt-1 text-xs text-stone-500">{dateTimeOrDash(redemption.created_at)}</p></li>)}</ul>
            )}
          </Card>
          <Card>
            <div className="flex items-center justify-between gap-2"><h2 className="font-black">{t("admin.payments")}</h2><span className="text-xs text-stone-500">{t("admin.payment.deferred")}</span></div>
            {payments.length === 0 ? <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p> : (
              <ul className="mt-2 flex flex-col gap-2">{payments.map((payment) => <li key={payment.id} className="rounded-xl bg-stone-50 px-3 py-2 text-sm"><p className="font-bold" dir="ltr">#{faNum(payment.id)} {payment.plan_code}</p><p className="mt-1 text-xs text-stone-500">{adminStatusLabel(payment.status)} · {faNum(payment.final_amount_minor)} <span dir="ltr">{payment.currency}</span> · {t("admin.providerLabel")}: {paymentProviderLabel(payment.provider)} · {dateTimeOrDash(payment.created_at)}</p></li>)}</ul>
            )}
          </Card>
        </div>
      ) : null}
      {tab === "timeline" ? (
        <Card>
          <h2 className="font-black">{t("admin.users.activity")}</h2>
          {timeline.length === 0 ? <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p> : (
            <ol className="mt-3 flex flex-col gap-3">
              {timeline.map((item, index) => (
                <li key={`${item.kind}-${index}`} className="border-r-2 border-violet-200 pr-3">
                  <p className="font-black">{eventLabel(item.kind)}</p>
                  <p className="mt-1 text-xs text-stone-500" dir="ltr">{faDateTime(item.at)}</p>
                  {item.detail ? <p className="mt-1 whitespace-pre-wrap text-sm text-stone-600">{timelineDetail(item.kind, item.detail)}</p> : null}
                </li>
              ))}
            </ol>
          )}
        </Card>
      ) : null}
    </div>
  );
}
