import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { adminApi } from "../api/client";
import type { UserProfileFull } from "../api/types";
import { AdminLayout } from "../components/admin/AdminLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum } from "../lib/playerDisplay";

type Tab = "overview" | "learning" | "commercial" | "timeline";

const TABS: Array<[Tab, string]> = [
  ["overview", "admin.overviewTab"],
  ["learning", "admin.learningTab"],
  ["commercial", "admin.commercialTab"],
  ["timeline", "admin.timelineTab"],
];

function eventLabel(kind: string): string {
  if (kind === "first_attempt") return t("admin.eventFirstAttempt");
  if (kind === "subscription") return t("admin.eventSubscription");
  if (kind === "payment") return t("admin.eventPayment");
  if (kind === "coupon") return t("admin.eventCoupon");
  if (kind === "recommendation") return t("admin.eventRecommendation");
  if (kind === "support") return t("admin.eventSupport");
  return t("admin.eventRegistered");
}

export function AdminUserDetailPage() {
  const { id } = useParams();
  const [tab, setTab] = useState<Tab>("overview");
  const [profile, setProfile] = useState<UserProfileFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!id) return;
    adminApi
      .userProfile(Number(id))
      .then((p) => {
        setProfile(p);
        setLoading(false);
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  }, [id]);

  return (
    <AdminLayout>
      <PageHeader title={t("admin.usersDetail")} subtitle={t("admin.subtitle")} />
      {loading ? (
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      ) : failed || !profile ? (
        <div className="py-8 text-center">
          <p className="text-stone-500">{t("common.error")}</p>
          <Button onClick={() => window.location.reload()} className="mx-auto mt-3 max-w-xs">
            {t("common.retry")}
          </Button>
        </div>
      ) : (
        <div>
          <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
            {TABS.map(([value, key]) => (
              <button
                key={value}
                type="button"
                onClick={() => setTab(value)}
                className={`min-h-[44px] shrink-0 rounded-full px-4 text-sm font-bold ${
                  tab === value ? "bg-violet-700 text-white" : "bg-violet-100 text-violet-700"
                }`}
              >
                {t(key as never)}
              </button>
            ))}
          </div>
          {tab === "overview" ? (
            <div className="flex flex-col gap-2">
              <Card>
                <p className="font-black" dir="ltr">{profile.overview.username}</p>
                <p className="text-sm text-stone-500">{profile.overview.display_name}</p>
                <p className="mt-1 text-xs text-stone-500" dir="ltr">
                  {profile.overview.roles.join(", ")} ·{" "}
                  {profile.overview.is_active ? t("admin.statusActive") : t("admin.statusSuspended")}
                </p>
              </Card>
              <div className="grid grid-cols-2 gap-2">
                <Card className="text-center">
                  <p className="text-2xl font-black text-violet-700">{faNum(profile.overview.attempts_total)}</p>
                  <p className="mt-1 text-xs text-stone-500">{t("admin.attempts")}</p>
                </Card>
                <Card className="text-center">
                  <p className="text-sm font-black text-violet-700" dir="ltr">{profile.overview.created_at.slice(0, 10)}</p>
                  <p className="mt-1 text-xs text-stone-500">{t("admin.registered")}</p>
                </Card>
              </div>
              <Card>
                <p className="text-sm text-stone-500">
                  {t("admin.lastActive")}:{" "}
                  <span dir="ltr">{profile.overview.last_active_at ?? "—"}</span>
                </p>
              </Card>
            </div>
          ) : null}
          {tab === "learning" ? (
            <div className="flex flex-col gap-2">
              <div className="grid grid-cols-3 gap-2">
                <Card className="text-center">
                  <p className="text-xl font-black text-violet-700" dir="ltr">{profile.learning.overall_level}</p>
                  <p className="mt-1 text-xs text-stone-500">{t("admin.level")}</p>
                </Card>
                <Card className="text-center">
                  <p className="text-xl font-black text-violet-700">{faNum(profile.learning.xp?.total ?? 0)}</p>
                  <p className="mt-1 text-xs text-stone-500">{t("admin.totalXp")}</p>
                </Card>
                <Card className="text-center">
                  <p className="text-xl font-black text-violet-700">{faNum(profile.learning.streak?.current ?? 0)}</p>
                  <p className="mt-1 text-xs text-stone-500">{t("admin.currentStreak")}</p>
                </Card>
              </div>
              <Card>
                <h2 className="font-black">{t("admin.skillsSeen")}</h2>
                {profile.learning.skills.length === 0 ? (
                  <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
                ) : (
                  <ul className="mt-2 flex flex-col gap-1">
                    {profile.learning.skills.map((s) => (
                      <li key={s.skill} className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3 text-sm">
                        <span dir="ltr" className="font-bold">{s.skill}</span>
                        <span dir="ltr" className="text-stone-500">{s.level} · {s.confidence}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
              <Card>
                <h2 className="font-black">{t("admin.exerciseUsage")}</h2>
                {profile.learning.attempts_by_exercise.length === 0 ? (
                  <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
                ) : (
                  <ul className="mt-2 flex flex-col gap-1">
                    {profile.learning.attempts_by_exercise.map((row) => (
                      <li key={row.exercise_slug} className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3 text-sm">
                        <span dir="ltr" className="font-bold">{row.exercise_slug}</span>
                        <span>{faNum(row.attempts)} · {faNum(row.correct)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          ) : null}
          {tab === "commercial" ? (
            <div className="flex flex-col gap-2">
              <Card>
                <h2 className="font-black">{t("admin.subscriptions")}</h2>
                {!profile.commercial.current_subscription ? (
                  <p className="mt-1 text-sm text-stone-500">{t("admin.noSubscription")}</p>
                ) : (
                  <p className="mt-1 text-sm">
                    <span dir="ltr">
                      {profile.commercial.current_subscription.plan_code} ·{" "}
                      {profile.commercial.current_subscription.status}
                    </span>{" "}
                    · {t("admin.sourceLabel")}:{" "}
                    <span dir="ltr">{profile.commercial.current_subscription.source}</span>
                  </p>
                )}
              </Card>
              <Card>
                <h2 className="font-black">{t("admin.campaigns")}</h2>
                {!profile.commercial.attribution ? (
                  <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
                ) : (
                  <p className="mt-1 text-xs text-stone-500">
                    {t("admin.sourceLabel")}:{" "}
                    <span dir="ltr">
                      {profile.commercial.attribution.first_source}/
                      {profile.commercial.attribution.first_campaign || "—"}
                    </span>{" "}
                    · {t("admin.couponCode")}:{" "}
                    <span dir="ltr">{profile.commercial.attribution.first_coupon_code || "—"}</span>
                  </p>
                )}
              </Card>
              <Card>
                <h2 className="font-black">{t("admin.coupons")}</h2>
                {profile.commercial.redemptions.length === 0 ? (
                  <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
                ) : (
                  <ul className="mt-2 flex flex-col gap-1">
                    {profile.commercial.redemptions.map((r, i) => (
                      <li key={`${r.code}-${i}`} className="rounded-xl bg-stone-50 px-3 py-2 text-xs">
                        <span dir="ltr">{r.code} · {r.status}</span> · {t("admin.discountValue")}:{" "}
                        {faNum(r.discount_granted_minor)} · {t("admin.trialDays")}: {faNum(r.trial_days_granted)}
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
              <Card>
                <h2 className="font-black">{t("admin.payments")}</h2>
                {profile.commercial.payments.length === 0 ? (
                  <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
                ) : (
                  <ul className="mt-2 flex flex-col gap-1">
                    {profile.commercial.payments.map((p) => (
                      <li key={p.id} className="rounded-xl bg-stone-50 px-3 py-2 text-xs">
                        #{p.id} <span dir="ltr">{p.plan_code} · {p.status}</span> ·{" "}
                        {faNum(p.final_amount_minor)} <span dir="ltr">{p.currency}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          ) : null}
          {tab === "timeline" ? (
            <div className="flex flex-col gap-2">
              <Card>
                <h2 className="font-black">{t("admin.userTimeline")}</h2>
                {profile.timeline.length === 0 ? (
                  <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
                ) : (
                  <ul className="mt-2 flex flex-col gap-1">
                    {profile.timeline.map((item, i) => (
                      <li key={`${item.kind}-${i}`} className="rounded-xl bg-stone-50 px-3 py-2">
                        <p className="text-sm font-bold">{eventLabel(item.kind)}</p>
                        <p className="text-xs text-stone-500" dir="ltr">
                          {item.at} · {item.detail}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </div>
          ) : null}
        </div>
      )}
    </AdminLayout>
  );
}
