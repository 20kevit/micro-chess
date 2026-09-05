import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import type { AttemptMode, AttemptResponse, Puzzle } from "../../api/types";
import { t } from "../../i18n";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { PageHeader } from "../ui/PageHeader";

const faNum = (n: number) => n.toLocaleString("fa-IR");

// Blindfold task payload (visible). The FEN is never exposed: only the
// Persian description, side to move and mode travel to the client.
function asTask(puzzle: Puzzle): { description: string; side: string } | null {
  const raw = puzzle.position_json;
  if (typeof raw.description_fa !== "string" || typeof raw.side_to_move !== "string") {
    return null;
  }
  return { description: raw.description_fa, side: raw.side_to_move };
}

function correctMoveOf(result: AttemptResponse): string | null {
  const raw = result.detail.correct_move;
  return typeof raw === "string" && raw.length > 0 ? raw : null;
}

// Text-answer play loop for Blindfold Calculation (Mate in 1). Same Entry →
// Play → Feedback → Next shape and primitives as the other play loops
// (attempts, timing, hints), but deliberately renders NO chessboard, NO
// piece images and NO FEN: the Persian position description is the whole
// interface. The backend validates the SAN authoritatively.
export function BlindfoldCalculationPlay() {
  const [started, setStarted] = useState(false);
  const [mode, setMode] = useState<AttemptMode>("practice");

  if (!started) {
    return (
      <div>
        <PageHeader title={t("exercises.blindfold-calculation.title")} subtitle={t("blindfoldCalculation.intro")} />
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

  return <BlindfoldMateLoop mode={mode} onChangeMode={setMode} />;
}

function BlindfoldMateLoop({
  mode,
  onChangeMode,
}: {
  mode: AttemptMode;
  onChangeMode: (m: AttemptMode) => void;
}) {
  const [puzzles, setPuzzles] = useState<Puzzle[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>(() => new Date().toISOString());
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setPuzzles(await api.listPuzzles("blindfold-calculation"));
    } catch {
      setError(t("common.error"));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const puzzle = puzzles?.[index] ?? null;
  const task = puzzle ? asTask(puzzle) : null;

  function resetForPuzzle() {
    setAnswer("");
    setUsedHints([]);
    setResult(null);
    setStartedAt(new Date().toISOString());
  }

  function goNext() {
    if (!puzzles?.length) return;
    setIndex((i) => (i + 1) % puzzles.length);
    resetForPuzzle();
  }

  const canSubmit = answer.trim().length > 0 && !submitting && result === null;

  async function submit() {
    if (!puzzle || !canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.submitAttempt({
        puzzle_id: puzzle.id,
        answer: { move: answer.trim() },
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
  if (puzzles.length === 0 || !puzzle || !task) {
    return (
      <Card>
        <Badge>{t("exercise.comingSoon")}</Badge>
        <p className="mt-2">{t("exercises.empty")}</p>
      </Card>
    );
  }

  const hints = puzzle.hint_json.hints ?? [];
  const correctMove = result ? correctMoveOf(result) : null;
  const isCorrect = result?.result === "correct";

  return (
    <div>
      <PageHeader title={t("exercises.blindfold-calculation.title")} subtitle={puzzle.prompt_fa} />
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
        <Badge>{task.side === "black" ? t("blindfoldCalculation.turnBlack") : t("blindfoldCalculation.turnWhite")}</Badge>
      </div>

      <Card>
        <p className="text-sm font-black text-stone-800">{t("blindfoldCalculation.position")}</p>
        <p className="mt-2 text-base leading-8 text-stone-800">{task.description}</p>
        <p className="mt-3 text-xs text-stone-400">{t("blindfoldCalculation.audioSoon")}</p>
      </Card>

      {!result ? (
        <div>
          <p className="mt-3 text-base font-black text-stone-800">{t("blindfoldCalculation.answer")}</p>
          <p className="mt-1 text-sm text-stone-500">{t("blindfoldCalculation.instruction")}</p>
          <div className="mt-2">
            <input
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submit();
              }}
              dir="ltr"
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
              disabled={submitting}
              aria-label={t("blindfoldCalculation.answer")}
              placeholder={t("blindfoldCalculation.answerPlaceholder")}
              className="min-h-[56px] w-full rounded-2xl border-2 border-stone-200 bg-white px-4 text-left text-2xl font-black text-stone-900 outline-none transition focus:border-violet-600"
              style={{ touchAction: "manipulation" }}
            />
          </div>
          <div className="mt-2 flex gap-2">
            <Button className="flex-1" onClick={() => submit()} disabled={!canSubmit}>
              {t("play.submit")}
            </Button>
            <Button variant="secondary" onClick={() => setAnswer("")} disabled={submitting}>
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
            {isCorrect ? t("blindfoldCalculation.correct") : t("blindfoldCalculation.wrong")}
          </p>
          {correctMove ? (
            <p className="mt-2 text-sm font-bold">
              {t("blindfoldCalculation.correctMove")}:{" "}
              <span dir="ltr" className="text-base font-black">
                {correctMove}
              </span>
            </p>
          ) : null}
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
