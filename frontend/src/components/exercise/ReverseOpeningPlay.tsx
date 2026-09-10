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

const PROMOTION_CHOICES = ["q", "r", "b", "n"] as const;

// Visible task payload. Both FENs render boards, but never the solution:
// the move sequence lives only in the server-side answer_json.
function asTask(puzzle: Puzzle): { startFen: string; targetFen: string; opening: string } | null {
  const raw = puzzle.position_json;
  if (
    typeof raw.start_fen !== "string" ||
    typeof raw.target_fen !== "string" ||
    typeof raw.opening_fa !== "string"
  ) {
    return null;
  }
  return { startFen: raw.start_fen, targetFen: raw.target_fen, opening: raw.opening_fa };
}

function detailStrings(result: AttemptResponse, key: "correct_sequence" | "submitted_sequence"): string[] {
  const raw = result.detail[key];
  return Array.isArray(raw) ? raw.filter((s): s is string => typeof s === "string") : [];
}

function detailNumber(result: AttemptResponse, key: "matched_plies" | "expected_plies"): number | null {
  const raw = result.detail[key];
  return typeof raw === "number" ? raw : null;
}

// Reconstruction play loop: the TARGET board (read-only, final position)
// stays on top; the user replays the opening from the START position on
// the second board. Every played move is validated by the backend step
// endpoint (legality only); grading happens at submit and compares full
// positions. The frontend never decides correctness.
export function ReverseOpeningPlay() {
  const [started, setStarted] = useState(false);
  const [mode, setMode] = useState<AttemptMode>("practice");

  if (!started) {
    return (
      <div>
        <PageHeader
          title={t("exercises.reverse-opening.title")}
          subtitle={t("reconstruction.intro")}
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

  return <ReconstructionLoop mode={mode} onChangeMode={setMode} />;
}

function ReconstructionLoop({
  mode,
  onChangeMode,
}: {
  mode: AttemptMode;
  onChangeMode: (m: AttemptMode) => void;
}) {
  const [puzzles, setPuzzles] = useState<Puzzle[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [fen, setFen] = useState<string>("");
  const [fenHistory, setFenHistory] = useState<string[]>([]);
  const [moves, setMoves] = useState<string[]>([]);
  const [sans, setSans] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [promotion, setPromotion] = useState<string>("q");
  const [pendingPromotion, setPendingPromotion] = useState<{ from: string; to: string } | null>(null);
  const [onTrack, setOnTrack] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>(() => new Date().toISOString());
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [stepBusy, setStepBusy] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setPuzzles(await api.listPuzzles("reverse-opening"));
    } catch {
      setError(t("common.error"));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const puzzle = puzzles?.[index] ?? null;
  const task = puzzle ? asTask(puzzle) : null;

  // Initialize the reconstruction board whenever the puzzle changes.
  useEffect(() => {
    if (task) {
      setFen(task.startFen);
      setFenHistory([]);
      setMoves([]);
      setSans([]);
      setSelected(null);
      setPromotion("q");
      setPendingPromotion(null);
      setOnTrack(true);
      setNotice(null);
      setUsedHints([]);
      setResult(null);
      setStartedAt(new Date().toISOString());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [puzzle?.id]);

  const targetPieces = useMemo(() => fenToPieces(task?.targetFen ?? null), [task]);
  const livePieces = useMemo(() => fenToPieces(fen || null), [fen]);

  function resetForPuzzle() {
    if (!task) return;
    setFen(task.startFen);
    setFenHistory([]);
    setMoves([]);
    setSans([]);
    setSelected(null);
    setPromotion("q");
    setPendingPromotion(null);
    setOnTrack(true);
    setNotice(null);
    setUsedHints([]);
    setResult(null);
    setStartedAt(new Date().toISOString());
  }

  function goNext() {
    if (!puzzles?.length) return;
    setIndex((i) => (i + 1) % puzzles.length);
  }

  function undo() {
    if (result || stepBusy || moves.length === 0) return;
    const prevFen = fenHistory[fenHistory.length - 1];
    setFenHistory((h) => h.slice(0, -1));
    setMoves((m) => m.slice(0, -1));
    setSans((s) => s.slice(0, -1));
    setFen(prevFen);
    setSelected(null);
    setPendingPromotion(null);
    setNotice(null);
  }

  async function playMove(from: string, to: string, promo: string | null) {
    if (!puzzle || !task || result || stepBusy) return;
    setStepBusy(true);
    setNotice(null);
    try {
      const res = await api.validateReverseOpeningStep({
        puzzle_id: puzzle.id,
        fen,
        moves,
        from,
        to,
        promotion: promo,
      });
      if (!res.ok) {
        if (res.message_key === "reconstruction.promotion") {
          setPendingPromotion({ from, to });
          setPromotion("q");
        } else {
          setNotice(t("reconstruction.invalid"));
        }
        return;
      }
      setFenHistory((h) => [...h, fen]);
      setFen(res.fen);
      setMoves(res.moves);
      setSans((s) => [...s, res.san]);
      setSelected(null);
      setPendingPromotion(null);
      setOnTrack(res.on_track);
      if (!res.on_track) setNotice(t("reconstruction.diverged"));
    } catch {
      setNotice(t("common.error"));
    } finally {
      setStepBusy(false);
    }
  }

  function tapSquare(square: string) {
    if (result || stepBusy) return;
    if (selected === null) {
      if (livePieces[square]) setSelected(square);
      return;
    }
    if (selected === square) {
      setSelected(null);
      return;
    }
    const from = selected;
    setSelected(null);
    playMove(from, square, null);
  }

  async function submit() {
    if (!puzzle || submitting || result || moves.length === 0) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.submitAttempt({
        puzzle_id: puzzle.id,
        answer: { moves },
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
  const isCorrect = result?.result === "correct";
  const matched = result ? detailNumber(result, "matched_plies") : null;
  const expected = result ? detailNumber(result, "expected_plies") : null;
  const shownSequence = result
    ? isCorrect
      ? detailStrings(result, "correct_sequence")
      : detailStrings(result, "submitted_sequence")
    : [];
  const exampleSequence = result && !isCorrect ? detailStrings(result, "correct_sequence") : [];

  const pendingPawn =
    pendingPromotion !== null &&
    (livePieces[pendingPromotion.from] === "P" || livePieces[pendingPromotion.from] === "p") &&
    (pendingPromotion.to.endsWith("8") || pendingPromotion.to.endsWith("1"));

  const squareStates: Partial<Record<string, "selected">> = {};
  if (selected) squareStates[selected] = "selected";

  return (
    <div>
      <PageHeader
        title={t("exercises.reverse-opening.title")}
        subtitle={puzzle.prompt_fa}
      />
      <div className="mb-3 flex flex-wrap items-center gap-2">
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

      <p className="mb-2 text-sm font-black text-stone-800">{t("reconstruction.target")}</p>
      <ChessBoard pieces={targetPieces} disabled />

      <p className="mb-2 mt-4 text-sm font-black text-stone-800">{t("reconstruction.board")}</p>
      <ChessBoard
        pieces={livePieces}
        onSquarePress={tapSquare}
        squareStates={squareStates}
        disabled={result !== null || stepBusy}
        draggablePieces
        onMove={(from, to) => playMove(from, to, null)}
      />

      {!result ? (
        <div>
          <p className="mt-3 text-sm text-stone-500">{t("reconstruction.instruction")}</p>
          {pendingPawn && pendingPromotion ? (
            <div className="mt-2">
              <p className="mb-1 text-sm text-stone-500">{t("reconstruction.promotion")}</p>
              <div className="flex gap-2" role="group" aria-label={t("reconstruction.promotion")}>
                {PROMOTION_CHOICES.map((choice) => (
                  <button
                    key={choice}
                    type="button"
                    aria-pressed={promotion === choice}
                    disabled={stepBusy}
                    onClick={() => setPromotion(choice)}
                    className={`min-h-[44px] min-w-[44px] flex-1 rounded-2xl border-2 text-base font-black uppercase transition ${
                      promotion === choice
                        ? "border-violet-600 bg-violet-50 text-violet-800"
                        : "border-stone-200 bg-white text-stone-700"
                    }`}
                    style={{ touchAction: "manipulation" }}
                  >
                    {choice}
                  </button>
                ))}
              </div>
              <Button
                className="mt-2 w-full"
                disabled={stepBusy}
                onClick={() => playMove(pendingPromotion.from, pendingPromotion.to, promotion)}
              >
                {t("play.submit")}
              </Button>
            </div>
          ) : null}
          {sans.length > 0 ? (
            <Card className="mt-3">
              <p className="text-sm font-black">{t("reconstruction.moves")}</p>
              <div className="mt-1 grid gap-1" dir="ltr">
                {sans.map((_, i) =>
                  i % 2 === 0 ? (
                    <p key={i} className="text-sm font-bold text-stone-700">
                      {Math.floor(i / 2) + 1}. {sans[i]}
                      {sans[i + 1] ? ` ${sans[i + 1]}` : ""}
                    </p>
                  ) : null,
                )}
              </div>
            </Card>
          ) : null}
          {!onTrack ? (
            <p className="mt-2 text-sm font-bold text-amber-600">{t("reconstruction.diverged")}</p>
          ) : null}
          {notice && onTrack ? (
            <p className="mt-2 text-sm font-bold text-red-600">{notice}</p>
          ) : null}
          <div className="mt-2 flex gap-2">
            <Button className="flex-1" onClick={() => submit()} disabled={submitting || moves.length === 0}>
              {t("play.submit")}
            </Button>
            <Button variant="secondary" onClick={undo} disabled={stepBusy || moves.length === 0}>
              {t("reconstruction.undo")}
            </Button>
            <Button variant="secondary" onClick={resetForPuzzle} disabled={stepBusy}>
              {t("reconstruction.reset")}
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
            {isCorrect ? t("reconstruction.correct") : t("reconstruction.wrong")}
          </p>
          {matched !== null && expected !== null && !isCorrect ? (
            <p className="mt-2 text-sm font-bold text-stone-600">
              {t("reconstruction.matched")}: <span dir="ltr">{`${matched} / ${expected}`}</span>
            </p>
          ) : null}
          {shownSequence.length > 0 ? (
            <p className="mt-2 text-sm font-bold" dir="ltr">
              {isCorrect ? t("reconstruction.correctSequence") : t("reconstruction.yourSequence")}:{" "}
              {shownSequence.join(" ")}
            </p>
          ) : null}
          {exampleSequence.length > 0 ? (
            <p className="mt-1 text-sm font-bold text-stone-600" dir="ltr">
              {t("reconstruction.correctSequence")}: {exampleSequence.join(" ")}
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
