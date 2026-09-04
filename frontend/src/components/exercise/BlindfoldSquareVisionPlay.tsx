import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import type { AttemptMode, AttemptResponse, Puzzle } from "../../api/types";
import type { FaKey } from "../../i18n/fa";
import { t } from "../../i18n";
import { ChessBoard } from "../chess/ChessBoard";
import { ChessPiece, type PieceSymbol } from "../chess/ChessPiece";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { PageHeader } from "../ui/PageHeader";

const faNum = (n: number) => n.toLocaleString("fa-IR");

const PIECE_NAME_KEYS: Record<string, FaKey> = {
  K: "pieces.king",
  Q: "pieces.queen",
  R: "pieces.rook",
  B: "pieces.bishop",
  N: "pieces.knight",
  P: "pieces.pawn",
};

function asTask(puzzle: Puzzle): { piece: string; color: string; from: string; to: string } | null {
  const raw = puzzle.position_json;
  if (
    typeof raw.piece !== "string" ||
    typeof raw.color !== "string" ||
    typeof raw.from !== "string" ||
    typeof raw.to !== "string"
  ) {
    return null;
  }
  return { piece: raw.piece, color: raw.color, from: raw.from, to: raw.to };
}

function pieceSymbol(piece: string, color: string): PieceSymbol {
  const letter = piece.toUpperCase();
  return (color === "black" ? letter.toLowerCase() : letter) as PieceSymbol;
}

// Numeric-answer play loop for Blindfold Square Vision. Same Entry → Play →
// Feedback → Next shape and primitives as the other play loops (attempts,
// timing, hints), but the board stays empty with neutral start/target
// markers and the answer is a large touch-friendly numeric input. The
// backend derives the correct distance authoritatively.
export function BlindfoldSquareVisionPlay({
  slug,
  titleKey,
  introKey,
}: {
  slug: string;
  titleKey: FaKey;
  introKey: FaKey;
}) {
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

  return <BlindfoldLoop slug={slug} titleKey={titleKey} mode={mode} onChangeMode={setMode} />;
}

function BlindfoldLoop({
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
  const [answer, setAnswer] = useState("");
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

  const parsed = /^\d+$/.test(answer.trim()) ? parseInt(answer.trim(), 10) : null;

  async function submit() {
    if (!puzzle || submitting || result || parsed === null) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.submitAttempt({
        puzzle_id: puzzle.id,
        answer: { moves: parsed },
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
  const path = Array.isArray(result?.detail.path)
    ? result.detail.path.filter((s): s is string => typeof s === "string")
    : [];
  const correctMoves = result?.detail.moves;

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

      <Card>
        <div className="flex items-center gap-3">
          <span className="block h-14 w-14 shrink-0">
            <ChessPiece symbol={pieceSymbol(task.piece, task.color)} />
          </span>
          <div className="text-sm font-bold text-stone-700">
            <p>
              {t("blindfold.piece")}: {t(PIECE_NAME_KEYS[task.piece.toUpperCase()] ?? "play.move")}
            </p>
            <p>
              {t("blindfold.color")}: {task.color === "black" ? t("blindfold.black") : t("blindfold.white")}
            </p>
            <p>
              <span dir="ltr">
                {t("blindfold.from")}: {task.from} · {t("blindfold.to")}: {task.to}
              </span>
            </p>
          </div>
        </div>
      </Card>

      <div className="mt-3">
        <ChessBoard
          pieces={{}}
          markers={{ [task.from]: "dot", [task.to]: "star" }}
          disabled={result !== null || submitting}
        />
      </div>

      {!result ? (
        <div>
          <p className="mt-3 text-base font-black text-stone-800">{t("blindfold.question")}</p>
          <div className="mt-2 flex gap-2">
            <input
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              inputMode="numeric"
              pattern="[0-9]*"
              autoComplete="off"
              disabled={submitting}
              aria-label={t("blindfold.question")}
              placeholder="۰"
              className="min-h-[56px] w-full rounded-2xl border-2 border-stone-200 bg-white px-4 text-center text-2xl font-black text-stone-900 outline-none transition focus:border-violet-600"
              style={{ touchAction: "manipulation" }}
            />
          </div>
          <div className="mt-2 flex gap-2">
            <Button className="flex-1" onClick={() => submit()} disabled={submitting || parsed === null}>
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
          {typeof correctMoves === "number" ? (
            <p className="mt-3 text-sm font-bold">
              {t("play.correctAnswer")}: {faNum(correctMoves)} {t("blindfold.moves")}
            </p>
          ) : null}
          {path.length > 0 ? (
            <p className="mt-1 text-sm font-bold text-stone-600" dir="ltr">
              {path.join(" → ")}
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
