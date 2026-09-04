import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { AttemptMode, AttemptResponse, Puzzle } from "../api/types";
import { ChessBoard } from "../components/chess/ChessBoard";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { fenToPieces } from "../lib/fen";

const SLUG = "piece-recognition";
const faNum = (n: number) => n.toLocaleString("fa-IR");

// Entry/detail → puzzle loop. Renders answers only; backend decides correctness.
export function PieceRecognitionPage() {
  const [started, setStarted] = useState(false);
  const [mode, setMode] = useState<AttemptMode>("practice");

  if (!started) {
    return (
      <div>
        <PageHeader title={t("piece.title")} subtitle={t("piece.intro")} />
        <Card>
          <p className="mb-1 text-sm text-stone-500">{t("piece.mode")}</p>
          <div className="flex gap-2">
            <Button
              variant={mode === "practice" ? "primary" : "ghost"}
              className="flex-1"
              onClick={() => setMode("practice")}
            >
              {t("piece.practice")}
            </Button>
            <Button
              variant={mode === "rated" ? "primary" : "ghost"}
              className="flex-1"
              onClick={() => setMode("rated")}
            >
              {t("piece.rated")}
            </Button>
          </div>
          <Button className="mt-4 w-full" onClick={() => setStarted(true)}>
            {t("piece.start")}
          </Button>
        </Card>
      </div>
    );
  }

  return <PiecePlay mode={mode} onChangeMode={setMode} />;
}

function PiecePlay({ mode, onChangeMode }: { mode: AttemptMode; onChangeMode: (m: AttemptMode) => void }) {
  const [puzzles, setPuzzles] = useState<Puzzle[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>(() => new Date().toISOString());
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setPuzzles(await api.listPuzzles(SLUG));
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
    setSelected([]);
    setUsedHints([]);
    setResult(null);
    setStartedAt(new Date().toISOString());
  }

  function goNext() {
    if (!puzzles?.length) return;
    setIndex((i) => (i + 1) % puzzles.length);
    resetForPuzzle();
  }

  function toggleSquare(square: string) {
    if (result) return; // Locked after submission; feedback shows states.
    setSelected((prev) => (prev.includes(square) ? prev.filter((s) => s !== square) : [...prev, square]));
  }

  async function submit(clientResult?: string) {
    if (!puzzle || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.submitAttempt({
        puzzle_id: puzzle.id,
        answer: { selected_squares: selected },
        mode,
        hints_used: usedHints,
        started_at: startedAt,
        client_result: clientResult ?? null,
      });
      setResult(res);
    } catch {
      setError(mode === "rated" ? t("piece.authRequired") : t("common.error"));
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
  const squareStates: Partial<Record<string, "selected" | "correct" | "missed" | "wrong">> = {};
  if (result) {
    for (const s of result.detail.correct) squareStates[s] = "correct";
    for (const s of result.detail.missed) squareStates[s] = "missed";
    for (const s of result.detail.wrong) squareStates[s] = "wrong";
  } else {
    for (const s of selected) squareStates[s] = "selected";
  }

  return (
    <div>
      <PageHeader title={t("piece.title")} subtitle={puzzle.prompt_fa} />
      <div className="mb-3 flex items-center gap-2">
        <Badge>
          {faNum(index + 1)} / {faNum(puzzles.length)}
        </Badge>
        <button
          className="min-h-[44px] rounded-full bg-violet-100 px-4 text-sm font-bold text-violet-700"
          onClick={() => onChangeMode(mode === "practice" ? "rated" : "practice")}
        >
          {mode === "practice" ? t("piece.practice") : t("piece.rated")}
        </button>
      </div>

      <ChessBoard
        pieces={pieces}
        onSquarePress={toggleSquare}
        squareStates={squareStates}
        disabled={result !== null || submitting}
      />

      {!result ? (
        <div>
          <p className="mt-3 text-sm font-bold text-stone-600">
            {t("piece.selected")}: {faNum(selected.length)}
          </p>
          <div className="mt-2 flex gap-2">
            <Button className="flex-1" onClick={() => submit()} disabled={submitting}>
              {t("piece.submit")}
            </Button>
            <Button variant="secondary" onClick={() => setSelected([])} disabled={submitting}>
              {t("piece.clear")}
            </Button>
          </div>
          {hints.length > 0 ? (
            <Card className="mt-3">
              <p className="text-sm font-black">{t("piece.hints")}</p>
              {hints.map((h) => {
                const revealed = usedHints.includes(h.id);
                return (
                  <div key={h.id} className="mt-2 flex items-center justify-between gap-2">
                    {revealed ? (
                      <p className="text-sm">{h.text_fa}</p>
                    ) : (
                      <Button variant="ghost" className="px-2" onClick={() => setUsedHints((p) => [...p, h.id])}>
                        {t("piece.useHint")}
                      </Button>
                    )}
                    {revealed ? <Badge>{t("piece.hintUsed")}</Badge> : null}
                  </div>
                );
              })}
            </Card>
          ) : null}
          {error ? <p className="mt-2 text-sm font-bold text-red-600">{error}</p> : null}
        </div>
      ) : (
        <Card className="mt-3">
          <div className="flex gap-4 text-center">
            <div className="flex-1">
              <p className="text-2xl font-black text-green-600">{faNum(result.detail.correct.length)}</p>
              <p className="text-xs text-stone-500">{t("piece.correctCount")}</p>
            </div>
            <div className="flex-1">
              <p className="text-2xl font-black text-amber-600">{faNum(result.detail.missed.length)}</p>
              <p className="text-xs text-stone-500">{t("piece.missedCount")}</p>
            </div>
            <div className="flex-1">
              <p className="text-2xl font-black text-red-600">{faNum(result.detail.wrong.length)}</p>
              <p className="text-xs text-stone-500">{t("piece.wrongCount")}</p>
            </div>
          </div>
          <p className="mt-3 text-sm font-bold">
            {t("piece.correctAnswer")}: {result.detail.correct.concat(result.detail.missed).join("، ")}
          </p>
          {puzzle.explanation ? (
            <p className="mt-2 text-sm text-stone-600">
              {t("piece.explanation")}: {puzzle.explanation}
            </p>
          ) : null}
          <div className="mt-3 flex gap-2">
            <Button className="flex-1" onClick={goNext}>
              {t("piece.next")}
            </Button>
            <Button variant="secondary" onClick={resetForPuzzle}>
              {t("piece.retry")}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
