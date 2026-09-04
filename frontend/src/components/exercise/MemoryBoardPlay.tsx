import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../api/client";
import type { AttemptMode, AttemptResponse, Puzzle } from "../../api/types";
import type { FaKey } from "../../i18n/fa";
import { t } from "../../i18n";
import { fenToPieces } from "../../lib/fen";
import { ChessBoard, type BoardMap } from "../chess/ChessBoard";
import { ChessPiece, type PieceSymbol } from "../chess/ChessPiece";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { PageHeader } from "../ui/PageHeader";

const faNum = (n: number) => n.toLocaleString("fa-IR");
const DEFAULT_MEMORIZE_SECONDS = 8;

const PALETTE: PieceSymbol[] = ["K", "Q", "R", "B", "N", "P", "k", "q", "r", "b", "n", "p"];

// Two-phase play loop for Memory Board. Same Entry → Play → Feedback → Next
// shape and primitives as the other play loops (board, attempts, timing,
// hints), but each puzzle is first shown read-only with a countdown and
// then rebuilt piece by piece on an empty board. The backend compares the
// reconstruction authoritatively.
export function MemoryBoardPlay({ slug, titleKey, introKey }: { slug: string; titleKey: FaKey; introKey: FaKey }) {
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

  return <MemoryLoop slug={slug} titleKey={titleKey} mode={mode} onChangeMode={setMode} />;
}

type Phase = "memorize" | "rebuild";

function memorizeSecondsOf(puzzle: Puzzle): number {
  const raw = puzzle.position_json.memorize_seconds;
  return typeof raw === "number" && Number.isInteger(raw) && raw > 0 ? raw : DEFAULT_MEMORIZE_SECONDS;
}

function MemoryLoop({
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
  const [phase, setPhase] = useState<Phase>("memorize");
  const [secondsLeft, setSecondsLeft] = useState(DEFAULT_MEMORIZE_SECONDS);
  const [placed, setPlaced] = useState<BoardMap>({});
  const [active, setActive] = useState<PieceSymbol | "eraser" | null>(null);
  const [turn, setTurn] = useState<"white" | "black">("white");
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

  const resetForPuzzle = useCallback(() => {
    if (!puzzle) return;
    setPhase("memorize");
    setSecondsLeft(memorizeSecondsOf(puzzle));
    setPlaced({});
    setActive(null);
    setTurn("white");
    setUsedHints([]);
    setResult(null);
    setStartedAt(new Date().toISOString());
  }, [puzzle]);

  // Restart progress whenever a new puzzle is shown.
  useEffect(() => {
    resetForPuzzle();
  }, [resetForPuzzle]);

  // Countdown during memorize; transition to rebuild exactly once at zero.
  useEffect(() => {
    if (phase !== "memorize" || !puzzle || secondsLeft <= 0) return;
    const timer = setTimeout(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          setPhase("rebuild");
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearTimeout(timer);
  }, [phase, puzzle, secondsLeft]);

  const memorized = useMemo(() => fenToPieces(puzzle?.fen ?? null), [puzzle]);

  function goNext() {
    if (!puzzles?.length) return;
    setIndex((i) => (i + 1) % puzzles.length);
  }

  function tapSquare(square: string) {
    if (phase !== "rebuild" || result || active === null) return;
    setPlaced((prev) => {
      const next: BoardMap = { ...prev };
      if (active === "eraser" || next[square] === active) {
        delete next[square];
      } else {
        next[square] = active;
      }
      return next;
    });
  }

  async function submit() {
    if (!puzzle || submitting || result) return;
    setSubmitting(true);
    setError(null);
    try {
      const entries = Object.entries(placed).filter(
        (entry): entry is [string, PieceSymbol] => entry[1] !== undefined,
      );
      const pieces = entries.map(([square, symbol]) => ({
        square,
        piece: symbol.toUpperCase(),
        color: symbol === symbol.toUpperCase() ? "white" : "black",
      }));
      const res = await api.submitAttempt({
        puzzle_id: puzzle.id,
        answer: { pieces, turn },
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
  const placedCount = Object.keys(placed).length;

  if (phase === "memorize") {
    return (
      <div>
        <PageHeader title={t(titleKey)} subtitle={t("memory.memorize")} />
        <div className="mb-3 flex items-center gap-2">
          <Badge>
            {faNum(index + 1)} / {faNum(puzzles.length)}
          </Badge>
          <Badge>
            {faNum(secondsLeft)} {t("memory.seconds")}
          </Badge>
        </div>
        <ChessBoard pieces={memorized} disabled />
      </div>
    );
  }

  const squareStates: Partial<Record<string, "selected" | "correct" | "missed" | "wrong" | "target">> = {};
  if (result) {
    for (const s of result.detail.correct) squareStates[s] = "correct";
    for (const s of result.detail.missed) squareStates[s] = "missed";
    for (const s of result.detail.wrong) squareStates[s] = "wrong";
  }

  return (
    <div>
      <PageHeader title={t(titleKey)} subtitle={t("memory.rebuild")} />
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
        pieces={placed}
        squareStates={squareStates}
        onSquarePress={tapSquare}
        disabled={result !== null || submitting}
      />

      {!result ? (
        <div>
          <p className="mt-3 text-sm font-bold text-stone-600">
            {t("memory.pieces")}: {faNum(placedCount)}
          </p>
          <div className="mt-2 grid grid-cols-7 gap-1" role="group" aria-label={t("memory.palette")}>
            {PALETTE.map((symbol) => {
              const isActive = active === symbol;
              return (
                <button
                  key={symbol}
                  type="button"
                  aria-pressed={isActive}
                  onClick={() => setActive(isActive ? null : symbol)}
                  className={`aspect-square min-h-[44px] rounded-xl border-2 p-1 transition ${
                    isActive ? "border-violet-600 bg-violet-50" : "border-stone-200 bg-white"
                  }`}
                  style={{ touchAction: "manipulation" }}
                >
                  <ChessPiece symbol={symbol} />
                </button>
              );
            })}
            <button
              type="button"
              aria-pressed={active === "eraser"}
              onClick={() => setActive(active === "eraser" ? null : "eraser")}
              className={`aspect-square min-h-[44px] rounded-xl border-2 text-lg font-black transition ${
                active === "eraser" ? "border-violet-600 bg-violet-50 text-violet-800" : "border-stone-200 bg-white text-stone-500"
              }`}
              style={{ touchAction: "manipulation" }}
              aria-label={t("memory.eraser")}
            >
              ⌫
            </button>
          </div>
          <div className="mt-2 flex gap-2" role="group" aria-label={t("play.mode")}>
            <Button
              variant={turn === "white" ? "primary" : "ghost"}
              className="flex-1"
              onClick={() => setTurn("white")}
            >
              {t("memory.turnWhite")}
            </Button>
            <Button
              variant={turn === "black" ? "primary" : "ghost"}
              className="flex-1"
              onClick={() => setTurn("black")}
            >
              {t("memory.turnBlack")}
            </Button>
          </div>
          <div className="mt-2 flex gap-2">
            <Button className="flex-1" onClick={() => submit()} disabled={submitting}>
              {t("play.submit")}
            </Button>
            <Button variant="secondary" onClick={() => setPlaced({})} disabled={submitting}>
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
            <Button variant="secondary" onClick={() => resetForPuzzle()}>
              {t("play.retry")}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
