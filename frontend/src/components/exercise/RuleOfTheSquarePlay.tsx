import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../api/client";
import type { AttemptMode, AttemptResponse, Puzzle } from "../../api/types";
import { t } from "../../i18n";
import { fenToPieces } from "../../lib/fen";
import { ChessBoard } from "../chess/ChessBoard";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { PageHeader } from "../ui/PageHeader";

const faNum = (n: number) => n.toLocaleString("fa-IR");

const CHOICES = ["CAN_CATCH", "CANNOT_CATCH"] as const;

function detailStrings(result: AttemptResponse, key: "corners"): string[] {
  const raw = result.detail[key];
  return Array.isArray(raw) ? raw.filter((s): s is string => typeof s === "string") : [];
}

// Classification play loop for Rule of the Square. The board is always
// visible (the exercise is about seeing the geometry), but the square
// itself is never drawn before submission: only after grading do the
// corner markers appear. The backend decides correctness authoritatively.
export function RuleOfTheSquarePlay() {
  const [started, setStarted] = useState(false);
  const [mode, setMode] = useState<AttemptMode>("practice");

  if (!started) {
    return (
      <div>
        <PageHeader
          title={t("exercises.rule-of-the-square.title")}
          subtitle={t("square.intro")}
        />
        <Card>
          <p className="mb-1 text-sm text-stone-500">{t("play.mode")}</p>
          <div className="flex gap-2">
            <Button
              variant={mode === "practice" ? "primary" : "ghost"}
              className="flex-1"
              onClick={() => setMode("practice")}
            >
              {t("play.practice")}
            </Button>
            <Button
              variant={mode === "rated" ? "primary" : "ghost"}
              className="flex-1"
              onClick={() => setMode("rated")}
            >
              {t("play.rated")}
            </Button>
          </div>
          <Button className="mt-4 w-full" onClick={() => setStarted(true)}>
            {t("play.start")}
          </Button>
        </Card>
      </div>
    );
  }

  return <SquareLoop mode={mode} onChangeMode={setMode} />;
}

function SquareLoop({
  mode,
  onChangeMode,
}: {
  mode: AttemptMode;
  onChangeMode: (m: AttemptMode) => void;
}) {
  const [puzzles, setPuzzles] = useState<Puzzle[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>(() => new Date().toISOString());
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setPuzzles(await api.listPuzzles("rule-of-the-square"));
    } catch {
      setError(t("common.error"));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const puzzle = puzzles?.[index] ?? null;
  const pieces = useMemo(() => fenToPieces(puzzle?.fen ?? null), [puzzle]);

  function resetForPuzzle() {
    setSelected(null);
    setUsedHints([]);
    setResult(null);
    setStartedAt(new Date().toISOString());
  }

  function goNext() {
    if (!puzzles?.length) return;
    setIndex((i) => (i + 1) % puzzles.length);
    resetForPuzzle();
  }

  async function submit() {
    if (!puzzle || submitting || result || selected === null) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.submitAttempt({
        puzzle_id: puzzle.id,
        answer: { answer: selected },
        mode,
        hints_used: usedHints,
        started_at: startedAt,
      });
      setResult(res);
    } catch {
      setError(mode === "rated" ? t("play.authRequired") : t("common.error"));
    } finally {
      setSubmitting(false);
    }
  }

  if (error && puzzles === null) {
    return (
      <Card>
        <p>{error}</p>
        <Button className="mt-3" onClick={load}>
          {t("common.retry")}
        </Button>
      </Card>
    );
  }
  if (puzzles === null) return <p>{t("common.loading")}</p>;
  if (puzzles.length === 0 || !puzzle) {
    return (
      <Card>
        <Badge>{t("exercise.comingSoon")}</Badge>
        <p className="mt-2">{t("exercises.empty")}</p>
      </Card>
    );
  }

  const hints = puzzle.hint_json.hints ?? [];
  const isCorrect = result?.result === "correct";
  const corners = result ? detailStrings(result, "corners") : [];
  const markers: Partial<Record<string, "star" | "dot">> = {};
  for (const corner of corners) markers[corner] = "dot";

  return (
    <div>
      <PageHeader
        title={t("exercises.rule-of-the-square.title")}
        subtitle={puzzle.prompt_fa}
      />
      <div className="mb-3 flex items-center gap-2">
        <Badge>
          {faNum(index + 1)} / {faNum(puzzles.length)}
        </Badge>
        <button
          className="min-h-[44px] rounded-full bg-violet-100 px-4 text-sm font-bold text-violet-700"
          onClick={() => onChangeMode(mode === "practice" ? "rated" : "practice")}
        >
          {mode === "practice" ? t("play.practice") : t("play.rated")}
        </button>
      </div>

      <ChessBoard pieces={pieces} markers={markers} disabled />

      {!result ? (
        <div>
          <div className="mt-3 grid gap-2">
            {CHOICES.map((choice) => {
              const active = selected === choice;
              const label = choice === "CAN_CATCH" ? t("square.can") : t("square.cannot");
              return (
                <button
                  key={choice}
                  type="button"
                  aria-pressed={active}
                  disabled={submitting}
                  onClick={() => setSelected(choice)}
                  className={`flex min-h-[56px] items-center justify-center rounded-2xl border-2 px-4 py-3 text-lg font-black transition ${
                    active
                      ? "border-violet-600 bg-violet-50 text-violet-800"
                      : "border-stone-200 bg-white text-stone-700"
                  }`}
                  style={{ touchAction: "manipulation" }}
                >
                  {label}
                </button>
              );
            })}
          </div>
          <div className="mt-2 flex gap-2">
            <Button className="flex-1" onClick={() => submit()} disabled={submitting || selected === null}>
              {t("play.submit")}
            </Button>
            <Button variant="secondary" onClick={() => setSelected(null)} disabled={submitting}>
              {t("play.clear")}
            </Button>
          </div>
          {hints.length > 0 ? (
            <Card className="mt-3">
              <p className="text-sm font-black">{t("play.hints")}</p>
              {hints.map((h) => {
                const revealed = usedHints.includes(h.id);
                return (
                  <div key={h.id} className="mt-2 flex items-center justify-between gap-2">
                    {revealed ? (
                      <p className="text-sm">{h.text_fa}</p>
                    ) : (
                      <Button variant="ghost" className="px-2" onClick={() => setUsedHints((p) => [...p, h.id])}>
                        {t("play.useHint")}
                      </Button>
                    )}
                    {revealed ? <Badge>{t("play.hintUsed")}</Badge> : null}
                  </div>
                );
              })}
            </Card>
          ) : null}
          {error ? <p className="mt-2 text-sm font-bold text-red-600">{error}</p> : null}
        </div>
      ) : (
        <Card className="mt-3">
          <p className={`text-lg font-black ${isCorrect ? "text-green-700" : "text-red-600"}`}>
            {isCorrect ? t("square.correct") : t("square.wrong")}
          </p>
          {puzzle.explanation ? (
            <p className="mt-2 text-sm text-stone-600">
              {t("play.explanation")}: {puzzle.explanation}
            </p>
          ) : null}
          <div className="mt-3 flex gap-2">
            <Button className="flex-1" onClick={goNext}>
              {t("play.next")}
            </Button>
            <Button variant="secondary" onClick={resetForPuzzle}>
              {t("play.retry")}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
