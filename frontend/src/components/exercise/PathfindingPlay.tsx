import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../api/client";
import type { AttemptMode, AttemptResponse, Puzzle } from "../../api/types";
import type { FaKey } from "../../i18n/fa";
import { t } from "../../i18n";
import { fenToPieces } from "../../lib/fen";
import { ChessBoard } from "../chess/ChessBoard";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { PageHeader } from "../ui/PageHeader";

const faNum = (n: number) => n.toLocaleString("fa-IR");

// Multi-step play loop for Pathfinding. Same Entry → Play → Feedback → Next
// shape and primitives as ExercisePlay (board, attempts, timing, hints),
// but the board position evolves move by move: each drag is validated by the
// backend step endpoint, and reaching the star auto-submits the full path
// as one attempt. The backend replays the whole path authoritatively.
export function PathfindingPlay({ slug, titleKey, introKey }: { slug: string; titleKey: FaKey; introKey: FaKey }) {
  const [started, setStarted] = useState(false);
  const [mode, setMode] = useState<AttemptMode>("practice");

  if (!started) {
    return (
      <div>
        <PageHeader title={t(titleKey)} subtitle={t(introKey)} />
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

  return <PathLoop slug={slug} titleKey={titleKey} mode={mode} onChangeMode={setMode} />;
}

function asString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function PathLoop({
  slug,
  titleKey,
  mode,
  onChangeMode,
}: {
  slug: string;
  titleKey: FaKey;
  mode: AttemptMode;
  onChangeMode: (m: AttemptMode) => void;
}) {
  const [puzzles, setPuzzles] = useState<Puzzle[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [fen, setFen] = useState<string | null>(null);
  const [selectedAt, setSelectedAt] = useState<string | null>(null);
  const [path, setPath] = useState<string[]>([]);
  const [stepBusy, setStepBusy] = useState(false);
  const [stepError, setStepError] = useState<string | null>(null);
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>(() => new Date().toISOString());
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setPuzzles(await api.listPuzzles(slug));
    } catch {
      setError(t("common.error"));
    }
  }, [slug]);

  useEffect(() => {
    load();
  }, [load]);

  const puzzle = puzzles?.[index] ?? null;
  const start = puzzle ? asString(puzzle.position_json.from) : null;
  const target = puzzle ? asString(puzzle.position_json.target) : null;

  const resetPath = useCallback(() => {
    if (!puzzle) return;
    setFen(puzzle.fen);
    setSelectedAt(start);
    setPath(start ? [start] : []);
    setStepError(null);
    setResult(null);
    setUsedHints([]);
    setStartedAt(new Date().toISOString());
  }, [puzzle, start]);

  // Restart progress whenever a new puzzle is shown.
  useEffect(() => {
    resetPath();
  }, [resetPath]);

  const pieces = useMemo(() => fenToPieces(fen), [fen]);

  function goNext() {
    if (!puzzles?.length) return;
    setIndex((i) => (i + 1) % puzzles.length);
  }

  async function submitPath(finalPath: string[]) {
    if (!puzzle || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.submitAttempt({
        puzzle_id: puzzle.id,
        answer: { path: finalPath },
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

  async function handleMove(from: string, to: string) {
    if (!puzzle || result || stepBusy || submitting) return;
    if (from !== selectedAt) return; // only the selected piece moves
    setStepBusy(true);
    try {
      const res = await api.validatePathStep({
        puzzle_id: puzzle.id,
        fen: fen ?? puzzle.fen ?? "",
        selected_at: selectedAt ?? "",
        from,
        to,
      });
      if (!res.ok) {
        setStepError(t("pathfinding.invalid"));
        return;
      }
      const nextPath = [...path, res.selected_at];
      setFen(res.fen);
      setSelectedAt(res.selected_at);
      setPath(nextPath);
      setStepError(null);
      if (res.reached) await submitPath(nextPath);
    } catch {
      setStepError(t("common.error"));
    } finally {
      setStepBusy(false);
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
  if (puzzles.length === 0 || !puzzle || !start || !target) {
    return (
      <Card>
        <Badge>{t("exercise.comingSoon")}</Badge>
        <p className="mt-2">{t("exercises.empty")}</p>
      </Card>
    );
  }

  const hints = puzzle.hint_json.hints ?? [];
  const squareStates: Partial<Record<string, "selected" | "correct" | "missed" | "wrong" | "target">> = {};
  if (result) {
    for (const s of result.detail.correct) squareStates[s] = "correct";
    for (const s of result.detail.missed) squareStates[s] = "missed";
    for (const s of result.detail.wrong) squareStates[s] = "wrong";
  } else if (selectedAt) {
    squareStates[selectedAt] = "selected";
  }

  return (
    <div>
      <PageHeader title={t(titleKey)} subtitle={puzzle.prompt_fa} />
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

      <ChessBoard
        pieces={pieces}
        squareStates={squareStates}
        markers={{ [target]: "star" }}
        disabled={result !== null || submitting || stepBusy}
        draggablePieces
        draggableSquares={selectedAt ? [selectedAt] : []}
        arrowsEnabled={false}
        onMove={handleMove}
      />

      {!result ? (
        <div>
          <p className="mt-3 text-sm font-bold text-stone-600">
            {t("pathfinding.moves")}: {faNum(Math.max(0, path.length - 1))}
          </p>
          {stepError ? <p className="mt-1 text-sm font-bold text-red-600">{stepError}</p> : null}
          <div className="mt-2 flex gap-2">
            <Button variant="secondary" className="flex-1" onClick={resetPath} disabled={stepBusy}>
              {t("play.retry")}
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
          <div className="flex gap-4 text-center">
            <div className="flex-1">
              <p className="text-2xl font-black text-green-600">{faNum(result.detail.correct.length)}</p>
              <p className="text-xs text-stone-500">{t("play.correctCount")}</p>
            </div>
            <div className="flex-1">
              <p className="text-2xl font-black text-amber-600">{faNum(result.detail.missed.length)}</p>
              <p className="text-xs text-stone-500">{t("play.missedCount")}</p>
            </div>
            <div className="flex-1">
              <p className="text-2xl font-black text-red-600">{faNum(result.detail.wrong.length)}</p>
              <p className="text-xs text-stone-500">{t("play.wrongCount")}</p>
            </div>
          </div>
          <p className="mt-3 text-sm font-bold">
            {t("play.correctAnswer")}: {result.detail.correct.concat(result.detail.missed).join("، ")}
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
            <Button variant="secondary" onClick={resetPath}>
              {t("play.retry")}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
