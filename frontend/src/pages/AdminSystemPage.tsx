import { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import type { AdminJourneyOverview, ProviderHealth, SystemHealth } from "../api/types";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum, faPercent } from "../lib/playerDisplay";

function providerLabel(configured: boolean | undefined, available: boolean | undefined): string {
  if (configured === undefined && available === undefined) return t("admin.notAvailable");
  if (available === undefined) return t("admin.notAvailable");
  if (!configured && !available) return t("admin.health.notConnected");
  if (available) return t("admin.health.operational");
  if (configured) return t("admin.health.disabledTemporarily");
  return t("admin.health.notConnected");
}

function channelLabel(channel: string): string {
  if (channel === "in_app") return t("notif.channel.in_app");
  if (channel === "web_push") return t("admin.health.push");
  if (channel === "telegram") return t("admin.health.telegram");
  if (channel === "bale") return t("admin.health.bale");
  return t("admin.unknown");
}

function Signal({ label, value }: { label: string; value: string }) {
  return <div className="rounded-2xl bg-stone-50 p-3"><p className="text-xs text-stone-500">{label}</p><p className="mt-1 text-lg font-black text-violet-700">{value}</p></div>;
}

export function AdminSystemPage() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [providers, setProviders] = useState<ProviderHealth | null>(null);
  const [journey, setJourney] = useState<AdminJourneyOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = () => {
    setLoading(true);
    setFailed(false);
    const providerRequest = typeof adminApi.providerHealth === "function"
      ? adminApi.providerHealth().catch(() => null)
      : Promise.resolve(null);
    const journeyRequest = typeof adminApi.journeyOverview === "function"
      ? adminApi.journeyOverview().catch(() => null)
      : Promise.resolve(null);
    Promise.all([adminApi.systemHealth(), providerRequest, journeyRequest])
      .then(([nextHealth, nextProviders, nextJourney]) => {
        setHealth(nextHealth);
        setProviders(nextProviders);
        setJourney(nextJourney);
      })
      .catch(() => setFailed(true))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  if (loading) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (failed || !health) {
    return <div className="py-8 text-center"><p className="text-stone-500">{t("common.error")}</p><div className="mx-auto mt-3 max-w-xs"><Button onClick={load} className="w-full">{t("common.retry")}</Button></div></div>;
  }

  const providerData = providers ?? health.providers ?? null;
  const channels = providerData?.channels ?? health.channels ?? {};
  const billing = providerData?.billing;

  return (
    <div>
      <PageHeader title={t("admin.system")} subtitle={t("admin.systemSubtitle")} />
      <div className="flex flex-col gap-3">
        <Card>
          <h2 className="font-black">{t("admin.health.overview")}</h2>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
            <div className="rounded-2xl bg-stone-50 p-3"><p className="text-xs text-stone-500">{t("admin.health.application")}</p><p className="mt-1 font-black">{health.ok ? t("admin.health.operational") : t("admin.unhealthy")}</p></div>
            <div className="rounded-2xl bg-stone-50 p-3"><p className="text-xs text-stone-500">{t("admin.health.database")}</p><p className="mt-1 font-black">{health.database?.reachable ? t("admin.reachable") : t("admin.unreachable")}</p></div>
            <div className="rounded-2xl bg-stone-50 p-3"><p className="text-xs text-stone-500">{t("admin.health.schema")}</p><p className="mt-1 font-black" dir="ltr">{health.schema_status?.expected ?? "—"} → {health.schema_status?.stored ?? "—"}</p><p className="mt-1 text-xs text-stone-500">{health.schema_status?.ok ? t("admin.healthy") : t("admin.unhealthy")}</p></div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2"><Signal label={t("admin.puzzlesPublished")} value={`${faNum(health.puzzles?.published ?? 0)}/${faNum(health.puzzles?.total ?? 0)}`} /><Signal label={t("admin.sysStatus")} value={health.ok ? t("admin.healthy") : t("admin.unhealthy")} /></div>
        </Card>
        <Card>
          <h2 className="font-black">{t("admin.health.providers")}</h2>
          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
            <div className="rounded-2xl bg-stone-50 p-3"><p className="text-sm font-bold">{t("admin.health.push")}</p><p className="mt-1 text-sm">{providerLabel(providerData?.vapid?.configured, providerData?.vapid?.available)}</p><p className="mt-1 text-xs text-stone-500">{t("admin.health.configured")}: {providerData?.vapid?.configured ? t("admin.yes") : t("admin.no")}</p></div>
            <div className="rounded-2xl bg-stone-50 p-3"><p className="text-sm font-bold">{t("admin.health.telegram")}</p><p className="mt-1 text-sm">{providerLabel(providerData?.telegram?.configured, providerData?.telegram?.available)}</p><p className="mt-1 text-xs text-stone-500">{t("admin.health.configured")}: {providerData?.telegram?.configured ? t("admin.yes") : t("admin.no")}</p></div>
                         <div className="rounded-2xl bg-stone-50 p-3"><p className="text-sm font-bold">{t("admin.health.verificationTelegram")}</p><p className="mt-1 text-sm">{providerData?.verification?.telegram_available ? t("admin.health.operational") : t("admin.health.disabledTemporarily")}</p></div>
             <div className="rounded-2xl bg-stone-50 p-3"><p className="text-sm font-bold">{t("admin.health.bale")}</p><p className="mt-1 text-sm">{providerLabel(providerData?.bale?.configured, providerData?.bale?.available)}</p><p className="mt-1 text-xs text-stone-500">{t("admin.health.configured")}: {providerData?.bale?.configured ? t("admin.yes") : t("admin.no")}</p></div>
            <div className="rounded-2xl bg-stone-50 p-3"><p className="text-sm font-bold">{t("admin.health.billing")}</p><p className="mt-1 text-sm" dir="ltr">{!billing ? t("admin.notAvailable") : billing.provider && billing.provider !== "none" ? t("admin.providerLabel") : t("admin.health.notConnected")}</p><p className="mt-1 text-xs text-stone-500">{billing ? providerLabel(billing.available, billing.available) : t("admin.notAvailable")}</p></div>
          </div>
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">{Object.entries(channels).map(([channel, value]) => <div key={channel} className="rounded-xl border border-stone-100 p-3"><p className="text-sm font-bold">{channelLabel(channel)}</p><p className="mt-1 text-xs text-stone-500">{providerLabel(value.configured, value.available)}</p>{value.subscriptions !== undefined ? <p className="mt-1 text-xs text-stone-500">{t("admin.health.push")}: {faNum(value.subscriptions)}</p> : null}{value.linked_users !== undefined ? <p className="mt-1 text-xs text-stone-500">{t("admin.label.user")}: {faNum(value.linked_users)}</p> : null}</div>)}</div>
        </Card>
        <Card>
          <h2 className="font-black">{t("admin.health.journey")}</h2>
          {!journey ? <p className="mt-2 text-sm text-stone-500">{t("admin.notAvailable")}</p> : <><div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4"><Signal label={t("onboarding.finish")} value={faNum(journey.onboarding_completed)} /><Signal label={t("placement.title")} value={faNum(journey.placement_completed)} /><Signal label={t("admin.sales.activations")} value={faNum(journey.premium_activations)} /><Signal label={t("admin.sales.freeUsers")} value={faNum(journey.free_users)} /><Signal label={t("admin.sales.premiumUsers")} value={faNum(journey.premium_users)} /><Signal label={t("admin.users.verification")} value={faNum(journey.phones_verified)} /><Signal label={t("admin.health.telegram")} value={faNum(journey.telegram_verified)} /><Signal label={t("admin.health.bale")} value={faNum(journey.bale_verified)} /><Signal label={t("admin.redemptions")} value={faNum(journey.coupon_redemptions)} /><Signal label={t("admin.health.dailyLimit")} value={faNum(journey.users_at_daily_limit)} /><Signal label={t("admin.health.failedNotifications")} value={faNum(journey.notification_delivery_failures)} /><Signal label={t("admin.health.questCompletion")} value={faPercent(journey.quest_completion_rate)} /><Signal label={t("journey.progress")} value={`${faNum(journey.quests_completed)}/${faNum(journey.quests_total)}`} /><Signal label={t("admin.health.push")} value={faNum(journey.push_subscriptions)} /><Signal label={t("admin.health.telegram")} value={faNum(journey.telegram_links)} /><Signal label={t("admin.health.bale")} value={faNum(journey.bale_links)} /><Signal label={t("admin.health.journey")} value={faNum(journey.quest_days)} /></div><p className="mt-3 text-xs text-stone-500">{t("admin.analytics.description")}</p></>}
        </Card>
      </div>
    </div>
  );
}
