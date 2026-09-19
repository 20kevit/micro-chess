import { useEffect, useState } from "react";
import { api, apiStatus } from "../api/client";
import type {
  AchievementItem,
  AttemptMode,
  GamificationSummary,
  HistoryAttempt,
  PlayerRating,
  ProgressSummary,
  XpHistoryItem,
} from "../api/types";
import { AnalyticsSection } from "../components/player/AnalyticsSection";
import { AdaptiveSection } from "../components/player/AdaptiveSection";
import { RecommendationSection } from "../components/player/RecommendationSection";
import { GamificationSection } from "../components/player/GamificationSection";
import { RatingsSection } from "../components/player/RatingsSection";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { exerciseTitle, faDate, faNum, faPercent, modeLabel, resultLabel } from "../lib/playerDisplay";

const PAGE_SIZE = 20;

// Player progress: own totals, per-exercise summary, and filterable history.
// All data is server-authoritative; filters only narrow the server query.
export function ProgressPage() {
  const [progress, setProgress] = useState<ProgressSummary | null>(null);
  const [history, setHistory] = useState<HistoryAttempt[]>([]);
  const [ratings, setRatings] = useState<PlayerRating[] | null>(null);
  const [ratingsFailed, setRatingsFailed] = useState(false);
  const [gamification, setGamification] = useState<GamificationSummary | null>(null);
  const [achievements, setAchievements] = useState<AchievementItem[] | null>(null);
  const [recentXp, setRecentXp] = useState<XpHistoryItem[] | null>(null);
  const [gamificationFailed, setGamificationFailed] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [exercise, setExercise] = useState("");
  const [mode, setMode] = useState<"" | AttemptMode>("");
  const [correct, setCorrect] = useState<"" | "true" | "false">("");
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setFailed(false);
    setRatings(null);
    setRatingsFailed(false);
    setGamification(null);
    setAchievements(null);
    setRecentXp(null);
    setGamificationFailed(false);
    // Ratings load independently: a ratings failure shows a section-level
    // error without hiding progress and history.
    api
      .getRatings()
      .then((res) => {
        if (!alive) return;
        setRatings(res.items);
      })
      .catch(() => {
        if (!alive) return;
        setRatingsFailed(true);
      });
    // Gamification loads independently with the same isolation.
    Promise.all([api.getGamification(), api.getAchievements(), api.getXpHistory()])
      .then(([summary, unlocked, history]) => {
        if (!alive) return;
        setGamification(summary);
        setAchievements(unlocked.items);
        setRecentXp(history.items.slice(0, 5));
      })
      .catch(() => {
        if (!alive) return;
        setGamificationFailed(true);
      });
    Promise.all([api.progress(), api.trainingAttempts({ page: 1, page_size: PAGE_SIZE })])
      .then(([summary, first]) => {
        if (!alive) return;
        setProgress(summary);
        setHistory(first);
        setPage(1);
        setHasMore(first.length === PAGE_SIZE);
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
  }, [retryKey]);

  async function applyFilters(nextExercise: string, nextMode: "" | AttemptMode, nextCorrect: "" | "true" | "false") {
    setExercise(nextExercise);
    setMode(nextMode);
    setCorrect(nextCorrect);
    try {
      const first = await api.trainingAttempts({
        exercise: nextExercise || undefined,
        mode: nextMode || undefined,
        correct: nextCorrect === "" ? undefined : nextCorrect === "true",
        page: 1,
        page_size: PAGE_SIZE,
      });
      setHistory(first);
      setPage(1);
      setHasMore(first.length === PAGE_SIZE);
    } catch (e) {
      if (apiStatus(e) === 401) return;
      setFailed(true);
    }
  }

  async function loadMore() {
    const next = page + 1;
    const rows = await api.trainingAttempts({
      exercise: exercise || undefined,
      mode: mode || undefined,
      correct: correct === "" ? undefined : correct === "true",
      page: next,
      page_size: PAGE_SIZE,
    });
    setHistory((prev) => [...prev, ...rows]);
    setPage(next);
    setHasMore(rows.length === PAGE_SIZE);
  }

  function retryGamification() {
    setGamification(null);
    setAchievements(null);
    setRecentXp(null);
    setGamificationFailed(false);
    Promise.all([api.getGamification(), api.getAchievements(), api.getXpHistory()])
      .then(([summary, unlocked, history]) => {
        setGamification(summary);
        setAchievements(unlocked.items);
        setRecentXp(history.items.slice(0, 5));
      })
      .catch(() => setGamificationFailed(true));
  }

  if (loading) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (failed || !progress)
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

  return (
    <div>
      <PageHeader title={t("progress.title")} subtitle={t("progress.subtitle")} />
      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-3 gap-2">
          <Card className="text-center">
            <p className="text-2xl font-black text-violet-700">{faNum(progress.attempts)}</p>
            <p className="mt-1 text-xs text-stone-500">{t("player.totalAttempts")}</p>
          </Card>
          <Card className="text-center">
            <p className="text-2xl font-black text-emerald-700">{faNum(progress.correct)}</p>
            <p className="mt-1 text-xs text-stone-500">{t("player.correctCount")}</p>
          </Card>
          <Card className="text-center">
            <p className="text-2xl font-black text-sky-700">{faPercent(progress.accuracy)}</p>
            <p className="mt-1 text-xs text-stone-500">{t("player.accuracy")}</p>
          </Card>
        </div>
        <RatingsSection
          ratings={ratings}
          failed={ratingsFailed}
          onRetry={() => {
            setRatings(null);
            setRatingsFailed(false);
            api
              .getRatings()
              .then((res) => setRatings(res.items))
              .catch(() => setRatingsFailed(true));
          }}
        />
        <GamificationSection
          summary={gamification}
          achievements={achievements}
          recentXp={recentXp}
          failed={gamificationFailed}
          onRetry={retryGamification}
        />
        <AnalyticsSection />
        <RecommendationSection />
        <AdaptiveSection />
        <Card>
          <h2 className="font-black">{t("player.perExercise")}</h2>
          {progress.exercises.length === 0 ? (
            <p className="mt-2 text-sm text-stone-500">{t("progress.empty")}</p>
          ) : (
            <ul className="mt-2 flex flex-col gap-2">
              {progress.exercises.map((entry) => (
                <li
                  key={entry.exercise}
                  className="flex min-h-[44px] flex-col justify-center gap-1 rounded-xl bg-stone-50 px-3 py-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-bold">{exerciseTitle(entry.exercise)}</span>
                    <span className="text-sm text-stone-500">
                      {faNum(entry.correct)} / {faNum(entry.attempts)} · {faPercent(entry.accuracy)}
                    </span>
                  </div>
                  <p className="text-xs text-stone-500">
                    {t("player.lastPracticed")}: {faDate(entry.last_practiced_at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <h2 className="font-black">{t("progress.history")}</h2>
          <div className="mt-2 grid grid-cols-3 gap-2">
            <label className="flex flex-col gap-1 text-xs text-stone-500">
              {t("progress.filterExercise")}
              <select
                value={exercise}
                onChange={(e) => void applyFilters(e.target.value, mode, correct)}
                className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-2 text-sm font-bold text-stone-900"
              >
                <option value="">{t("progress.allExercises")}</option>
                {progress.exercises.map((entry) => (
                  <option key={entry.exercise} value={entry.exercise}>
                    {exerciseTitle(entry.exercise)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-stone-500">
              {t("progress.filterMode")}
              <select
                value={mode}
                onChange={(e) => void applyFilters(exercise, e.target.value as "" | AttemptMode, correct)}
                className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-2 text-sm font-bold text-stone-900"
              >
                <option value="">{t("progress.allModes")}</option>
                <option value="practice">{t("play.practice")}</option>
                <option value="rated">{t("play.rated")}</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-stone-500">
              {t("progress.filterResult")}
              <select
                value={correct}
                onChange={(e) => void applyFilters(exercise, mode, e.target.value as "" | "true" | "false")}
                className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-2 text-sm font-bold text-stone-900"
              >
                <option value="">{t("progress.allResults")}</option>
                <option value="true">{t("progress.onlyCorrect")}</option>
                <option value="false">{t("progress.onlyWrong")}</option>
              </select>
            </label>
          </div>
          {history.length === 0 ? (
            <p className="mt-3 text-sm text-stone-500">{t("progress.empty")}</p>
          ) : (
            <ul className="mt-2 flex flex-col gap-2">
              {history.map((attempt) => (
                <li
                  key={attempt.id}
                  className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2"
                >
                  <span>
                    <span className="font-bold">{exerciseTitle(attempt.exercise_slug)}</span>{" "}
                    <span className="text-xs text-stone-500">
                      {modeLabel(attempt.mode)} · {faDate(attempt.created_at)}
                    </span>
                  </span>
                  <Badge>{resultLabel(attempt.result)}</Badge>
                </li>
              ))}
            </ul>
          )}
          {hasMore && history.length > 0 ? (
            <div className="mt-3">
              <Button variant="secondary" onClick={() => void loadMore()} className="w-full">
                {t("progress.more")}
              </Button>
            </div>
          ) : null}
        </Card>
      </div>
    </div>
  );
}
