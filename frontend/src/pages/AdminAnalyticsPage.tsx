import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../api/client";
import type {
  AdminExerciseAnalytics,
  AdminPlatformAnalytics,
  AdminPuzzleAnalytics,
  LearningOverview,
  RecommendationOverview,
  RetentionData,
} from "../api/types";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import {
  exerciseTitle,
  faDate,
  faNum,
  faPercent,
  observedDifficultyLabel,
} from "../lib/playerDisplay";

type Period = "7d" | "30d" | "90d" | "all" | "custom";
type BaseParams = { period: Period; date_from?: string; date_to?: string };
type PuzzleParams = {
  period?: string;
  exercise?: string;
  page?: number;
  page_size?: number;
  date_from?: string;
  date_to?: string;
};

const PERIODS: Period[] = ["7d", "30d", "90d", "all", "custom"];

function periodLabel(period: Period): string {
  if (period === "7d") return t("analytics.period7");
  if (period === "30d") return t("analytics.period30");
  if (period === "90d") return t("analytics.period90");
  if (period === "all") return t("analytics.periodAll");
  return t("admin.analytics.custom");
}

function safeExerciseTitle(slug: string): string {
  const title = exerciseTitle(slug);
  return title === slug ? t("admin.unknown") : title;
}

function metricCodeLabel(value: string): string {
  if (value === "insufficient_data") return t("admin.observedUnknown");
  if (value === "active") return t("admin.statusActive");
  if (value === "completed" || value === "shown" || value === "accepted") return t("admin.status.verified");
  if (value === "skipped") return t("feedback.skipped");
  if (value === "positive") return t("admin.evidence.positive");
  if (value === "negative") return t("admin.evidence.negative");
  if (value === "neutral") return t("admin.evidence.neutral");
  return t("admin.user.mistakes");
}

function recommendationStatus(value: string): string {
  if (value === "active" || value === "completed" || value === "shown" || value === "accepted") return t("admin.status.verified");
  if (value === "skipped") return t("feedback.skipped");
  return t("admin.recommendations");
}

function safeDifficulty(value: string): string {
  const label = observedDifficultyLabel(value);
  return label === value ? t("admin.unknown") : label;
}

function optionalRate(value: number | null | undefined): string {
  return value === null || value === undefined ? t("admin.notAvailable") : faPercent(value);
}

function Metric({ label, value, title }: { label: string; value: string; title?: string }) {
  return (
    <Card>
      <p className="text-xs text-stone-500" title={title}>{label}</p>
      <p className="mt-1 text-2xl font-black text-violet-700">{value}</p>
    </Card>
  );
}

export function AdminAnalyticsPage() {
  const [period, setPeriod] = useState<Period>("7d");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [rangeError, setRangeError] = useState(false);
  const [overview, setOverview] = useState<AdminPlatformAnalytics | null>(null);
  const [exercises, setExercises] = useState<AdminExerciseAnalytics[] | null>(null);
  const [puzzles, setPuzzles] = useState<AdminPuzzleAnalytics[] | null>(null);
  const [retention, setRetention] = useState<RetentionData | null>(null);
  const [learning, setLearning] = useState<LearningOverview | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let alive = true;
    const custom = period === "custom";
    if (custom && (!dateFrom || !dateTo)) {
      setRangeError(true);
      setLoading(false);
      setOverview(null);
      setExercises(null);
      setPuzzles(null);
      return () => {
        alive = false;
      };
    }
    setRangeError(false);
    setLoading(true);
    setFailed(false);
    const base: BaseParams = custom
      ? { period, date_from: dateFrom, date_to: dateTo }
      : { period };
    const puzzleBase: PuzzleParams = {
      period,
      page_size: 20,
      ...(custom ? { date_from: dateFrom, date_to: dateTo } : {}),
    };
    Promise.all([
      adminApi.platformAnalytics(base),
      adminApi.exerciseAnalytics(base),
      adminApi.puzzleAnalytics(puzzleBase),
      typeof adminApi.retention === "function" ? adminApi.retention().catch(() => null) : Promise.resolve(null),
      typeof adminApi.learning === "function" ? adminApi.learning(30).catch(() => null) : Promise.resolve(null),
      typeof adminApi.recommendationStats === "function" ? adminApi.recommendationStats(30).catch(() => null) : Promise.resolve(null),
    ])
      .then(([platform, byExercise, byPuzzle, ret, learn, recs]) => {
        if (!alive) return;
        setOverview(platform);
        setExercises(byExercise);
        setPuzzles(byPuzzle);
        setRetention(ret);
        setLearning(learn);
        setRecommendations(recs);
      })
      .catch(() => {
        if (alive) setFailed(true);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [dateFrom, dateTo, period, retryKey]);

  function selectPeriod(next: Period) {
    setPeriod(next);
    if (next !== "custom") {
      setRangeError(false);
    }
  }

  if (rangeError) {
    return (
      <div>
        <PageHeader title={t("admin.analytics")} subtitle={t("admin.analytics.description")} />
        <Card>
          <label className="block text-sm font-bold" htmlFor="admin-analytics-from">{t("admin.analytics.from")}</label>
          <input id="admin-analytics-from" type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm" />
          <label className="mt-3 block text-sm font-bold" htmlFor="admin-analytics-to">{t("admin.analytics.to")}</label>
          <input id="admin-analytics-to" type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm" />
          <p className="mt-2 text-sm text-red-600">{t("common.error")}</p>
        </Card>
        <div className="mt-3 flex justify-end">
          <select value={period} onChange={(event) => selectPeriod(event.target.value as Period)} aria-label={t("admin.analytics")} className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-bold">
            {PERIODS.map((value) => <option key={value} value={value}>{periodLabel(value)}</option>)}
          </select>
        </div>
      </div>
    );
  }

  if (loading) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (failed || !overview || !exercises || !puzzles) {
    return (
      <div className="py-8 text-center">
        <p className="text-stone-500">{t("common.error")}</p>
        <div className="mx-auto mt-3 max-w-xs"><Button onClick={() => setRetryKey((value) => value + 1)} className="w-full">{t("common.retry")}</Button></div>
      </div>
    );
  }

  const activeExercises = exercises.filter((exercise) => exercise.attempts > 0);
  const comparison = overview.comparison;

  return (
    <div>
      <PageHeader title={t("admin.analytics")} subtitle={t("admin.analytics.description")} />
      <Card>
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm text-stone-500">{t("admin.analytics.description")}</p>
            <p className="mt-1 text-xs text-stone-500" title={t("admin.analytics.explainSuccess")}>{t("admin.analytics.explainSuccess")}</p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <select value={period} onChange={(event) => selectPeriod(event.target.value as Period)} aria-label={t("admin.analytics")} className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-bold">
              {PERIODS.map((value) => <option key={value} value={value}>{periodLabel(value)}</option>)}
            </select>
            {period === "custom" ? (
              <>
                <label className="text-xs font-bold" htmlFor="admin-analytics-from">{t("admin.analytics.from")}<input id="admin-analytics-from" type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} className="mt-1 block min-h-[44px] rounded-xl border border-stone-200 bg-white px-2 text-sm" /></label>
                <label className="text-xs font-bold" htmlFor="admin-analytics-to">{t("admin.analytics.to")}<input id="admin-analytics-to" type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} className="mt-1 block min-h-[44px] rounded-xl border border-stone-200 bg-white px-2 text-sm" /></label>
              </>
            ) : null}
          </div>
        </div>
      </Card>
      <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
        <Metric label={t("admin.usersTotal")} value={faNum(overview.users_total)} title={t("admin.analytics.description")} />
        <Metric label={t("admin.newRegistrations")} value={faNum(overview.new_registrations)} title={t("admin.analytics.description")} />
        <Metric label={t("admin.activeUsers")} value={faNum(overview.active_users)} title={t("admin.analytics.description")} />
        <Metric label={t("admin.attemptsTotal")} value={faNum(overview.totals.attempts)} title={t("admin.analytics.description")} />
        <Metric label={t("player.accuracy")} value={faPercent(overview.totals.accuracy)} title={t("admin.analytics.explainSuccess")} />
        <Metric label={t("analytics.xpEarned")} value={faNum(overview.xp.earned_in_period)} title={t("admin.analytics.description")} />
      </div>
      <div className="mt-3 flex flex-col gap-3">
        <Card>
          <div className="flex items-center justify-between gap-2"><div><h2 className="font-black">{t("admin.analytics.comparison")}</h2><p className="mt-1 text-xs text-stone-500">{t("analytics.previousPeriod")}</p></div><Link to="/admin/users" className="min-h-[44px] py-3 text-sm font-bold text-violet-700">{t("admin.users")}</Link></div>
          {!comparison ? <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p> : <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4"><div className="rounded-xl bg-stone-50 p-3"><p className="text-xs text-stone-500">{t("admin.attempts")}</p><p className="mt-1 font-black">{faNum(comparison.attempts)}</p></div><div className="rounded-xl bg-stone-50 p-3"><p className="text-xs text-stone-500">{t("player.accuracy")}</p><p className="mt-1 font-black">{faPercent(comparison.accuracy)}</p></div><div className="rounded-xl bg-stone-50 p-3"><p className="text-xs text-stone-500">{t("admin.activeUsers")}</p><p className="mt-1 font-black">{faNum(comparison.active_users)}</p></div><div className="rounded-xl bg-stone-50 p-3"><p className="text-xs text-stone-500">{t("analytics.xpEarned")}</p><p className="mt-1 font-black">{faNum(comparison.xp_earned)}</p></div></div>}
        </Card>
        <Card>
          <h2 className="font-black">{t("admin.exerciseUsage")}</h2>
          {activeExercises.length === 0 ? <p className="mt-2 text-sm text-stone-500">{t("analytics.empty")}</p> : <div className="mt-2 overflow-x-auto"><table className="w-full min-w-[820px] text-right text-sm"><thead className="text-xs text-stone-500"><tr><th className="p-2">{t("admin.label.exercise")}</th><th className="p-2">{t("admin.attempts")}</th><th className="p-2">{t("admin.uniquePlayers")}</th><th className="p-2">{t("player.accuracy")}</th><th className="p-2">{t("admin.analytics.openExercise")}</th></tr></thead><tbody>{activeExercises.map((entry) => <tr key={entry.exercise} className="border-t border-stone-100"><td className="p-2 font-bold">{safeExerciseTitle(entry.exercise)}</td><td className="p-2">{faNum(entry.attempts)}</td><td className="p-2">{faNum(entry.unique_players)}</td><td className="p-2">{faPercent(entry.accuracy)}</td><td className="p-2"><Link to={`/admin/exercises/${entry.exercise}`} className="font-bold text-violet-700">{t("admin.analytics.openExercise")}</Link></td></tr>)}</tbody></table></div>}
        </Card>
        <Card>
          <h2 className="font-black">{t("admin.retention")}</h2>
          {!retention || retention.cohorts.length === 0 ? <p className="mt-2 text-sm text-stone-500">{t("analytics.empty")}</p> : <div className="mt-2 overflow-x-auto"><table className="w-full min-w-[620px] text-right text-sm"><thead className="text-xs text-stone-500"><tr><th className="p-2">{t("admin.createdAt")}</th><th className="p-2">{t("admin.usersTotal")}</th>{retention.offsets.map((offset) => <th key={offset} className="p-2">{`${t("analytics.activeDays")} ${faNum(offset)}`}</th>)}</tr></thead><tbody>{retention.cohorts.slice(-7).map((row) => <tr key={row.cohort} className="border-t border-stone-100"><td className="p-2" dir="ltr">{faDate(row.cohort)}</td><td className="p-2">{faNum(row.size)}</td>{retention.offsets.map((offset) => <td key={offset} className="p-2">{optionalRate(row.rates[String(offset)])}</td>)}</tr>)}</tbody></table></div>}
        </Card>
        <Card>
          <h2 className="font-black">{t("admin.learning")}</h2>
          {!learning ? <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p> : <div className="mt-2 grid grid-cols-1 gap-3 md:grid-cols-2"><div><p className="text-sm font-bold">{t("admin.exerciseUsage")}</p>{learning.exercise_usage.length === 0 ? <p className="mt-1 text-sm text-stone-500">{t("analytics.empty")}</p> : <ul className="mt-1 flex flex-col gap-1">{learning.exercise_usage.map((row) => <li key={row.exercise_slug} className="flex justify-between rounded-xl bg-stone-50 px-3 py-2 text-xs"><span>{safeExerciseTitle(row.exercise_slug)}</span><span>{faNum(row.attempts)} · {optionalRate(row.success_rate)}</span></li>)}</ul>}</div><div><p className="text-sm font-bold">{t("admin.user.mistakes")}</p>{learning.mistake_distribution.length === 0 ? <p className="mt-1 text-sm text-stone-500">{t("analytics.empty")}</p> : <ul className="mt-1 flex flex-col gap-1">{learning.mistake_distribution.map((row) => <li key={row.mistake} className="flex justify-between rounded-xl bg-stone-50 px-3 py-2 text-xs"><span>{metricCodeLabel(row.mistake)}</span><span>{faNum(row.count)}</span></li>)}</ul>}<p className="mt-3 text-sm font-bold">{t("admin.user.recommendations")}</p>{learning.direction_distribution.length === 0 ? <p className="mt-1 text-sm text-stone-500">{t("analytics.empty")}</p> : <ul className="mt-1 flex flex-col gap-1">{learning.direction_distribution.map((row) => <li key={row.direction} className="flex justify-between rounded-xl bg-stone-50 px-3 py-2 text-xs"><span>{metricCodeLabel(row.direction)}</span><span>{faNum(row.count)}</span></li>)}</ul>}</div></div>}
        </Card>
        <Card>
          <h2 className="font-black">{t("admin.recommendations")}</h2>
          {!recommendations ? <p className="mt-2 text-sm text-stone-500">{t("admin.empty")}</p> : <div className="mt-2 grid grid-cols-1 gap-3 md:grid-cols-2"><div><p className="text-2xl font-black text-violet-700">{faNum(recommendations.total)}</p><p className="text-xs text-stone-500">{t("admin.recommendations")}</p></div><ul className="flex flex-col gap-1">{recommendations.by_status.map((row) => <li key={row.status} className="flex justify-between rounded-xl bg-stone-50 px-3 py-2 text-xs"><span>{recommendationStatus(row.status)}</span><span>{faNum(row.count)}</span></li>)}</ul></div>}
        </Card>
        <Card>
          <h2 className="font-black">{t("admin.puzzlePerformance")}</h2>
          {puzzles.length === 0 ? <p className="mt-2 text-sm text-stone-500">{t("analytics.empty")}</p> : <ul className="mt-2 flex flex-col gap-2">{puzzles.map((row) => <li key={row.puzzle_id} className="flex min-h-[44px] flex-wrap items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2"><div><p className="font-bold">{safeExerciseTitle(row.exercise_slug)} · #{faNum(row.puzzle_id)}</p><p className="mt-1 text-xs text-stone-500">{faNum(row.attempts)} · {faPercent(row.accuracy)} · {t("admin.failureRate")}: {faPercent(row.failure_rate)} · {t("admin.repeatedFailures")}: {faNum(row.repeated_failures)}</p></div><div className="flex items-center gap-2"><span className="text-xs text-stone-500">{safeDifficulty(row.observed_difficulty)}</span><Link to={`/admin/puzzles/${row.puzzle_id}`} className="min-h-[44px] py-3 text-sm font-bold text-violet-700">{t("admin.analytics.openPuzzle")}</Link></div></li>)}</ul>}
        </Card>
        <Card>
          <h2 className="font-black">{t("analytics.trend")}</h2>
          {overview.daily.length === 0 ? <p className="mt-2 text-sm text-stone-500">{t("analytics.empty")}</p> : <ul className="mt-2 flex flex-col gap-1">{overview.daily.slice(-14).map((bucket) => <li key={bucket.bucket_start} className="flex items-center justify-between rounded-xl bg-stone-50 px-3 py-2 text-xs"><span dir="ltr">{faDate(bucket.bucket_start)}</span><span>{t("admin.attempts")}: {faNum(bucket.attempts)} · {t("player.accuracy")}: {faPercent(bucket.accuracy)}</span></li>)}</ul>}
        </Card>
      </div>
    </div>
  );
}
