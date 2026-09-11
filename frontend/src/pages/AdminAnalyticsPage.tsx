import { useEffect, useState } from "react";
import { adminApi } from "../api/client";
import type {
  AdminExerciseAnalytics,
  AdminPlatformAnalytics,
  AdminPuzzleAnalytics,
} from "../api/types";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { exerciseTitle, faNum, faPercent } from "../lib/playerDisplay";

type Period = "7d" | "30d" | "90d" | "all";

const PERIODS: Period[] = ["7d", "30d", "90d", "all"];

function periodLabel(period: Period): string {
  if (period === "7d") return t("analytics.period7");
  if (period === "30d") return t("analytics.period30");
  if (period === "90d") return t("analytics.period90");
  return t("analytics.periodAll");
}

function observedLabel(code: string): string {
  if (code === "easy") return t("admin.observedEasy");
  if (code === "medium") return t("admin.observedMedium");
  if (code === "hard") return t("admin.observedHard");
  return t("admin.observedUnknown");
}

// Admin analytics: aggregate read-only platform, exercise, and puzzle
// metrics. Every number comes from /admin/analytics*; responses carry
// no secrets and puzzle rows never include answers.
export function AdminAnalyticsPage() {
  const [period, setPeriod] = useState<Period>("7d");
  const [overview, setOverview] = useState<AdminPlatformAnalytics | null>(null);
  const [exercises, setExercises] = useState<AdminExerciseAnalytics[] | null>(null);
  const [puzzles, setPuzzles] = useState<AdminPuzzleAnalytics[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setFailed(false);
    Promise.all([
      adminApi.platformAnalytics({ period }),
      adminApi.exerciseAnalytics({ period }),
      adminApi.puzzleAnalytics({ period, page_size: 20 }),
    ])
      .then(([platform, byExercise, byPuzzle]) => {
        if (!alive) return;
        setOverview(platform);
        setExercises(byExercise);
        setPuzzles(byPuzzle);
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

  if (loading) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (failed || !overview || !exercises || !puzzles)
    return (
      <div className="py-8 text-center">
        <p className="text-stone-500">{t("common.error")}</p>
        <div className="mx-auto mt-3 max-w-xs">
          <Button onClick={() => setRetryKey((k) => k + 1)} className="w-full">
            {t("common.retry")}
          </Button>
        </div>
      </div>
    );

  const activeExercises = exercises.filter((e) => e.attempts > 0);

  return (
    <div>
      <div className="flex items-center justify-between gap-2">
        <PageHeader title={t("admin.analytics")} subtitle={t("admin.subtitle")} />
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value as Period)}
          aria-label={t("admin.analytics")}
          className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-2 text-sm font-bold text-stone-900"
        >
          {PERIODS.map((p) => (
            <option key={p} value={p}>
              {periodLabel(p)}
            </option>
          ))}
        </select>
      </div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        <Card className="text-center">
          <p className="text-2xl font-black text-violet-700">{faNum(overview.users_total)}</p>
          <p className="mt-1 text-xs text-stone-500">{t("admin.usersTotal")}</p>
        </Card>
        <Card className="text-center">
          <p className="text-2xl font-black text-violet-700">{faNum(overview.new_registrations)}</p>
          <p className="mt-1 text-xs text-stone-500">{t("admin.newRegistrations")}</p>
        </Card>
        <Card className="text-center">
          <p className="text-2xl font-black text-violet-700">{faNum(overview.active_users)}</p>
          <p className="mt-1 text-xs text-stone-500">{t("admin.activeUsers")}</p>
        </Card>
        <Card className="text-center">
          <p className="text-2xl font-black text-violet-700">{faNum(overview.totals.attempts)}</p>
          <p className="mt-1 text-xs text-stone-500">{t("admin.attemptsTotal")}</p>
        </Card>
        <Card className="text-center">
          <p className="text-2xl font-black text-sky-700">{faPercent(overview.totals.accuracy)}</p>
          <p className="mt-1 text-xs text-stone-500">{t("player.accuracy")}</p>
        </Card>
        <Card className="text-center">
          <p className="text-2xl font-black text-emerald-700">{faNum(overview.xp.earned_in_period)}</p>
          <p className="mt-1 text-xs text-stone-500">{t("analytics.xpEarned")}</p>
        </Card>
      </div>
      <div className="mt-3 flex flex-col gap-3">
        <Card>
          <h2 className="font-black">{t("admin.exerciseUsage")}</h2>
          {activeExercises.length === 0 ? (
            <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p>
          ) : (
            <ul className="mt-2 flex flex-col gap-2">
              {activeExercises.map((entry) => (
                <li
                  key={entry.exercise}
                  className="flex min-h-[44px] flex-col justify-center gap-1 rounded-xl bg-stone-50 px-3 py-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold">{exerciseTitle(entry.exercise)}</span>
                    <span className="text-sm text-stone-500">
                      {faNum(entry.attempts)} · {faPercent(entry.accuracy)}
                    </span>
                  </div>
                  <p className="text-xs text-stone-500">
                    {t("admin.uniquePlayers")}: {faNum(entry.unique_players)} ·{" "}
                    {observedLabel(
                      entry.attempts < 5
                        ? "insufficient_data"
                        : entry.accuracy >= 0.7
                          ? "easy"
                          : entry.accuracy >= 0.4
                            ? "medium"
                            : "hard",
                    )}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <h2 className="font-black">{t("admin.puzzlePerformance")}</h2>
          {puzzles.length === 0 ? (
            <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p>
          ) : (
            <ul className="mt-2 flex flex-col gap-2">
              {puzzles.map((row) => (
                <li
                  key={row.puzzle_id}
                  className="flex min-h-[44px] flex-col justify-center gap-1 rounded-xl bg-stone-50 px-3 py-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold" dir="ltr">
                      #{faNum(row.puzzle_id)} {exerciseTitle(row.exercise_slug)}
                    </span>
                    <span className="text-sm text-stone-500">{observedLabel(row.observed_difficulty)}</span>
                  </div>
                  <p className="text-xs text-stone-500">
                    {faNum(row.attempts)} · {faPercent(row.accuracy)} · {t("admin.failureRate")}:{" "}
                    {faPercent(row.failure_rate)} · {t("admin.repeatedFailures")}:{" "}
                    {faNum(row.repeated_failures)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
