import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiStatus } from "../../api/client";
import type { AdaptiveNext, AdaptiveOverview } from "../../api/types";
import { t } from "../../i18n";
import {
  adaptiveReasonLabel,
  exerciseTitle,
  faNum,
  faPercent,
  observedDifficultyLabel,
} from "../../lib/playerDisplay";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";

// Player-facing adaptive training. Display-only: every signal, reason,
// and candidate comes from /me/adaptive*; the section only transports
// the learner's accept/skip choices back as outcome records.
export function AdaptiveSection() {
  const [overview, setOverview] = useState<AdaptiveOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const [next, setNext] = useState<AdaptiveNext | null>(null);
  const [nextExercise, setNextExercise] = useState<string | null>(null);
  const [nextLoading, setNextLoading] = useState(false);
  const [nextMissing, setNextMissing] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setFailed(false);
    setOverview(null);
    setNext(null);
    setNextExercise(null);
    setNextMissing(false);
    api
      .adaptiveOverview()
      .then((res) => {
        if (!alive) return;
        setOverview(res);
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

  async function requestNext(exercise: string) {
    setNextLoading(true);
    setNextMissing(false);
    setNext(null);
    try {
      const res = await api.adaptiveNext(exercise);
      setNext(res);
      setNextExercise(exercise);
    } catch (e) {
      if (apiStatus(e) === 404) setNextMissing(true);
      setNextExercise(exercise);
    } finally {
      setNextLoading(false);
    }
  }

  async function recordOutcome(status: "accepted" | "skipped") {
    if (!next) return;
    try {
      await api.adaptiveOutcome(next.recommendation_id, { status });
    } catch {
      // Outcome recording is advisory: the training link still works
      // when the record call fails.
    }
    if (status === "skipped") {
      setNext(null);
      setNextExercise(null);
    }
  }

  if (loading) {
    return (
      <Card>
        <h2 className="font-black">{t("adaptive.title")}</h2>
        <p className="mt-2 text-sm text-stone-500">{t("common.loading")}</p>
      </Card>
    );
  }
  if (failed || overview === null) {
    return (
      <Card>
        <h2 className="font-black">{t("adaptive.title")}</h2>
        <p className="mt-2 text-sm text-stone-500">{t("common.error")}</p>
        <Button onClick={() => setRetryKey((k) => k + 1)}>{t("common.retry")}</Button>
      </Card>
    );
  }

  const recommended = overview.recommended_exercise;
  return (
    <Card>
      <h2 className="font-black">{t("adaptive.title")}</h2>
      <p className="mt-1 text-xs text-stone-500">{t("adaptive.subtitle")}</p>
      {recommended === null ? (
        <p className="mt-2 text-sm text-stone-500">{t("adaptive.empty")}</p>
      ) : (
        <div className="mt-3 rounded-xl bg-violet-50 px-3 py-2">
          <p className="text-xs text-stone-500">{t("adaptive.recommended")}</p>
          <p className="mt-1 font-black text-violet-800">{exerciseTitle(recommended)}</p>
          {overview.reason ? (
            <p className="mt-1 text-sm text-stone-600">{adaptiveReasonLabel(overview.reason)}</p>
          ) : null}
          <div className="mt-3 flex flex-col gap-2">
            <Button onClick={() => void requestNext(recommended)} disabled={nextLoading}>
              {t("adaptive.getNext")}
            </Button>
          </div>
        </div>
      )}
      {nextMissing && nextExercise ? (
        <p className="mt-2 text-sm text-stone-500">{t("adaptive.noContent")}</p>
      ) : null}
      {next ? (
        <div className="mt-3 rounded-xl bg-stone-50 px-3 py-2">
          <p className="font-bold">{exerciseTitle(next.puzzle.exercise_slug)}</p>
          {next.puzzle.prompt_fa ? (
            <p className="mt-1 text-sm text-stone-600">{next.puzzle.prompt_fa}</p>
          ) : null}
          <p className="mt-1 text-xs text-stone-500">
            {`${t("adaptive.ability")}: ${faNum(Math.round(next.ability_rating))} · ${t("adaptive.target")}: ${faNum(Math.round(next.target_rating))} · ${t("adaptive.observed")}: ${observedDifficultyLabel(next.observed_difficulty)}`}
          </p>
          <p className="mt-1 text-sm">
            <Badge>{adaptiveReasonLabel(next.reason)}</Badge>
          </p>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <Link
              to={`/exercises/${next.puzzle.exercise_slug}`}
              onClick={() => void recordOutcome("accepted")}
              className="flex min-h-[44px] flex-1 items-center justify-center rounded-2xl bg-violet-600 px-3 text-sm font-bold text-white"
            >
              {t("adaptive.start")}
            </Link>
            <Button onClick={() => void recordOutcome("skipped")}>{t("adaptive.skip")}</Button>
          </div>
        </div>
      ) : null}
      {overview.exercises.length > 0 ? (
        <div className="mt-3">
          <p className="text-xs text-stone-500">{t("adaptive.byExercise")}</p>
          <ul className="mt-2 flex flex-col gap-2">
            {overview.exercises.map((row) => (
              <li
                key={row.exercise}
                className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2"
              >
                <span className="font-bold">{exerciseTitle(row.exercise)}</span>
                <span className="flex items-center gap-2">
                  <Badge>{adaptiveReasonLabel(row.reason)}</Badge>
                  <span className="text-sm text-stone-600">{faPercent(row.accuracy)}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Card>
  );
}
