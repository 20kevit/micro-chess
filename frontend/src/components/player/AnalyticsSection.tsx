import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { PlayerAnalytics, PlayerComparison } from "../../api/types";
import { t } from "../../i18n";
import { exerciseTitle, faDate, faNum, faPercent } from "../../lib/playerDisplay";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";

type Period = "7d" | "30d" | "90d" | "all";

const PERIODS: Period[] = ["7d", "30d", "90d", "all"];

function periodLabel(period: Period): string {
  if (period === "7d") return t("analytics.period7");
  if (period === "30d") return t("analytics.period30");
  if (period === "90d") return t("analytics.period90");
  return t("analytics.periodAll");
}

function deltaText(value: number, isPercent = false): string {
  if (value === 0) return t("analytics.noChange");
  const sign = value > 0 ? "+" : "−";
  const abs = Math.abs(value);
  const body = isPercent ? faPercent(abs).replace("٪", "") + "٪" : faNum(Math.round(abs * 100) / 100);
  return `${sign}${body}`;
}

// Player-facing training analytics: trends and period comparison over
// the player's own attempts. Display-only: every number comes from
// /me/analytics* and nothing here computes business state.
export function AnalyticsSection() {
  const [period, setPeriod] = useState<Period>("7d");
  const [data, setData] = useState<PlayerAnalytics | null>(null);
  const [comparison, setComparison] = useState<PlayerComparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setFailed(false);
    setData(null);
    setComparison(null);
    const params = { period };
    Promise.all([
      api.getAnalytics(params),
      // All-time has no previous equivalent period (server rejects it).
      period === "all" ? Promise.resolve(null) : api.getAnalyticsComparison(params),
    ])
      .then(([overview, compared]) => {
        if (!alive) return;
        setData(overview);
        setComparison(compared);
        setLoading(false);
      })
      .catch(() => {
        if (!alive) return;
        setFailed(true);
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [period, retryKey]);

  if (loading) {
    return (
      <Card>
        <h2 className="font-black">{t("analytics.title")}</h2>
        <p className="mt-2 text-sm text-stone-500">{t("common.loading")}</p>
      </Card>
    );
  }
  if (failed || !data) {
    return (
      <Card>
        <h2 className="font-black">{t("analytics.title")}</h2>
        <p className="mt-2 text-sm text-stone-500">{t("common.error")}</p>
        <div className="mt-3">
          <Button onClick={() => setRetryKey((k) => k + 1)} className="w-full">
            {t("common.retry")}
          </Button>
        </div>
      </Card>
    );
  }

  const totals = data.totals;
  const maxDaily = Math.max(1, ...data.daily.map((b) => b.attempts));

  return (
    <Card>
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-black">{t("analytics.title")}</h2>
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value as Period)}
          aria-label={t("analytics.title")}
          className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-2 text-sm font-bold text-stone-900"
        >
          {PERIODS.map((p) => (
            <option key={p} value={p}>
              {periodLabel(p)}
            </option>
          ))}
        </select>
      </div>
      <p className="mt-1 text-xs text-stone-500">{t("analytics.subtitle")}</p>
      {totals.attempts === 0 ? (
        <p className="mt-2 text-sm text-stone-500">{t("analytics.empty")}</p>
      ) : (
        <>
          <div className="mt-2 grid grid-cols-3 gap-2">
            <div className="rounded-xl bg-stone-50 px-2 py-2 text-center">
              <p className="text-xl font-black text-violet-700">{faNum(totals.attempts)}</p>
              <p className="mt-1 text-xs text-stone-500">{t("player.totalAttempts")}</p>
            </div>
            <div className="rounded-xl bg-stone-50 px-2 py-2 text-center">
              <p className="text-xl font-black text-sky-700">{faPercent(totals.accuracy)}</p>
              <p className="mt-1 text-xs text-stone-500">{t("player.accuracy")}</p>
            </div>
            <div className="rounded-xl bg-stone-50 px-2 py-2 text-center">
              <p className="text-xl font-black text-emerald-700">{faNum(totals.active_days)}</p>
              <p className="mt-1 text-xs text-stone-500">{t("analytics.activeDays")}</p>
            </div>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <div className="rounded-xl bg-stone-50 px-2 py-2 text-center">
              <p className="text-lg font-black text-stone-800">{faNum(data.xp.earned_in_period)}</p>
              <p className="mt-1 text-xs text-stone-500">{t("analytics.xpEarned")}</p>
            </div>
            <div className="rounded-xl bg-stone-50 px-2 py-2 text-center">
              <p className="text-lg font-black text-stone-800">
                {data.ratings.length === 0
                  ? "—"
                  : faNum(Math.round(data.ratings.reduce((sum, r) => sum + r.delta_in_period, 0) * 100) / 100)}
              </p>
              <p className="mt-1 text-xs text-stone-500">{t("analytics.ratingChange")}</p>
            </div>
          </div>
          {data.daily.length > 0 ? (
            <div className="mt-3">
              <h3 className="text-sm font-black">{t("analytics.trend")}</h3>
              <ul className="mt-2 flex max-h-56 flex-col gap-1 overflow-y-auto" dir="ltr">
                {data.daily.map((bucket) => (
                  <li key={bucket.bucket_start} className="flex items-center gap-2">
                    <span className="w-20 shrink-0 text-left text-xs text-stone-500" dir="rtl">
                      {faDate(`${bucket.bucket_start}T00:00:00`)}
                    </span>
                    <span className="flex h-5 flex-1 items-center overflow-hidden rounded bg-stone-100">
                      <span
                        className="h-full rounded bg-violet-400"
                        style={{ width: `${Math.round((bucket.attempts / maxDaily) * 100)}%` }}
                      />
                    </span>
                    <span className="w-8 shrink-0 text-right text-xs font-bold text-stone-700">
                      {faNum(bucket.attempts)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {comparison ? (
            <div className="mt-3">
              <h3 className="text-sm font-black">{t("analytics.comparison")}</h3>
              <ul className="mt-2 flex flex-col gap-1 text-sm">
                <li className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2">
                  <span className="text-stone-500">{t("player.totalAttempts")}</span>
                  <span className="font-bold">{deltaText(comparison.delta.attempts)}</span>
                </li>
                <li className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2">
                  <span className="text-stone-500">{t("player.accuracy")}</span>
                  <span className="font-bold">{deltaText(comparison.delta.accuracy, true)}</span>
                </li>
                <li className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2">
                  <span className="text-stone-500">{t("analytics.activeDays")}</span>
                  <span className="font-bold">{deltaText(comparison.delta.active_days)}</span>
                </li>
              </ul>
            </div>
          ) : null}
          {data.by_exercise.length > 0 ? (
            <div className="mt-3">
              <h3 className="text-sm font-black">{t("analytics.byExercise")}</h3>
              <ul className="mt-2 flex flex-col gap-2">
                {data.by_exercise.map((entry) => (
                  <li
                    key={entry.exercise}
                    className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2"
                  >
                    <span className="font-bold">{exerciseTitle(entry.exercise)}</span>
                    <span className="text-sm text-stone-500">
                      {faNum(entry.correct)} / {faNum(entry.attempts)} · {faPercent(entry.accuracy)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
      )}
    </Card>
  );
}
