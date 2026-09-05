import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api/client";
import type { AttemptResponse, Puzzle, SpeedSummary } from "../../api/types";
import { t } from "../../i18n";
import { fenToPieces } from "../../lib/fen";
import { savePracticeAttempt } from "../../lib/localProgress";
import { ChessBoard } from "../chess/ChessBoard";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FeedbackText, PageHeader } from "../ui/PageHeader";

const faNum = (n: number) => n.toLocaleString("fa-IR");

export type PieceMode = "practice" | "speed";

// Dedicated Practice + Speed loop for Piece Recognition. Renders and
// transports answers only; validation, scoring, and the speed clock stay
// backend-authoritative. Random puzzles come from POST .../next (practice)
// or the speed-session endpoints — never from a fixed demo list.
// The ?mode= URL param (set by the home card's Practice/Speed buttons —
// the buttons ARE the mode selection) picks the loop directly; there is no
// intermediate mode-selection screen.
export function PieceRecognitionPlay({ mode }: { mode: PieceMode }) {
  return mode === "practice" ? <PracticeLoop /> : <SpeedLoop />;
}

function useSelection() {
  const [selected, setSelected] = useState<string[]>([]);
  const toggle = useCallback((square: string) => {
    setSelected((prev) => (prev.includes(square) ? prev.filter((s) => s !== square) : [...prev, square]));
  }, []);
  const clear = useCallback(() => setSelected([]), []);
  return { selected, toggle, clear, setSelected };
}

function BoardSection({
  puzzle,
  selected,
  result,
  disabled,
  onToggle,
}: {
  puzzle: Puzzle;
  selected: string[];
  result: AttemptResponse | null;
  disabled: boolean;
  onToggle: (square: string) => void;
}) {
  const pieces = useMemo(() => fenToPieces(puzzle.fen), [puzzle]);
  const squareStates: Partial<Record<string, "selected" | "correct" | "missed" | "wrong">> = {};
  if (result) {
    for (const s of result.detail.correct) squareStates[s] = "correct";
    for (const s of result.detail.missed) squareStates[s] = "missed";
    for (const s of result.detail.wrong) squareStates[s] = "wrong";
  } else {
    for (const s of selected) squareStates[s] = "selected";
  }
  return (
    <div className="mx-auto w-full min-w-0 max-w-[520px]">
      <ChessBoard
        pieces={pieces}
        onSquarePress={result ? undefined : onToggle}
        squareStates={squareStates}
        disabled={disabled}
      />
    </div>
  );
}

function HintCard({ puzzle, usedHints, onUse }: { puzzle: Puzzle; usedHints: string[]; onUse: (id: string) => void }) {
  const hints = puzzle.hint_json.hints ?? [];
  if (hints.length === 0) return null;
  return (
    <Card className="mt-3">
      <p className="text-sm font-black">{t("play.hints")}</p>
      {hints.map((h) => {
        const revealed = usedHints.includes(h.id);
        return (
          <div key={h.id} className="mt-2 flex items-center justify-between gap-2">
            {revealed ? (
              <p className="text-sm">{h.text_fa}</p>
            ) : (
              <Button variant="ghost" className="px-2" onClick={() => onUse(h.id)}>
                {t("play.useHint")}
              </Button>
            )}
            {revealed ? <Badge>{t("play.hintUsed")}</Badge> : null}
          </div>
        );
      })}
    </Card>
  );
}

function ResultBanner({ result }: { result: AttemptResponse }) {
  const tone =
    result.result === "correct"
      ? "border-green-500 bg-green-50"
      : result.result === "partial"
        ? "border-amber-500 bg-amber-50"
        : "border-red-400 bg-red-50";
  return (
    <div className={`rounded-2xl border-2 px-4 py-3 ${tone}`}>
      <FeedbackText feedbackKey={result.feedback_key} />
      <div className="mt-2 flex gap-4 text-center">
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
    </div>
  );
}

function FeedbackLegend() {
  const rows = [
    { symbol: "✓", label: t("piece.legendCorrect"), cls: "text-green-700" },
    { symbol: "✕", label: t("piece.legendWrong"), cls: "text-red-600" },
    { symbol: "!", label: t("piece.legendMissed"), cls: "text-amber-600" },
  ];
  return (
    <ul className="mt-3 grid gap-1">
      {rows.map((row) => (
        <li key={row.label} className="flex items-center gap-2 text-sm font-bold text-stone-700">
          <span aria-hidden="true" className={`inline-block w-5 text-center text-base ${row.cls}`}>
            {row.symbol}
          </span>
          {row.label}
        </li>
      ))}
    </ul>
  );
}

function PracticeLoop() {
  const [puzzle, setPuzzle] = useState<Puzzle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>(() => new Date().toISOString());
  const [solved, setSolved] = useState(0);
  const [correctTotal, setCorrectTotal] = useState(0);
  const { selected, toggle, clear, setSelected } = useSelection();

  const loadNext = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPuzzle(await api.nextPracticePuzzle());
      setResult(null);
      setSelected([]);
      setUsedHints([]);
      setStartedAt(new Date().toISOString());
    } catch {
      setError(t("common.error"));
    } finally {
      setLoading(false);
    }
  }, [setSelected]);

  useEffect(() => {
    loadNext();
  }, [loadNext]);

  async function submit() {
    if (!puzzle || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await api.submitAttempt({
        puzzle_id: puzzle.id,
        answer: { selected_squares: selected },
        mode: "practice",
        hints_used: usedHints,
        started_at: startedAt,
      });
      setResult(res);
      setSolved((n) => n + 1);
      if (res.result === "correct") setCorrectTotal((n) => n + 1);
      savePracticeAttempt(puzzle.id, res.score);
    } catch {
      setError(t("common.error"));
    } finally {
      setSubmitting(false);
    }
  }

  if (loading && !puzzle) return <p>{t("common.loading")}</p>;
  if (!puzzle) {
    return (
      <Card>
        <p>{error ?? t("common.error")}</p>
        <Button className="mt-3" onClick={loadNext}>
          {t("common.retry")}
        </Button>
      </Card>
    );
  }

  return (
    <div className="min-w-0">
      <PageHeader title={t("piece.title")} subtitle={puzzle.prompt_fa} />
      <div className="mb-3 flex min-w-0 items-center gap-2">
        <Badge>{t("play.practice")}</Badge>
        <Badge>
          {t("practice.solved")}: {faNum(solved)} · {t("play.correctCount")}: {faNum(correctTotal)}
        </Badge>
      </div>

      <BoardSection
        puzzle={puzzle}
        selected={selected}
        result={result}
        disabled={result !== null || submitting || loading}
        onToggle={toggle}
      />

      {!result ? (
        <div>
          <p className="mt-3 text-sm font-bold text-stone-600">
            {t("play.selected")}: {faNum(selected.length)}
          </p>
          <p className="mt-1 text-xs text-stone-500">{t("piece.emptyAllowed")}</p>
          <div className="mt-2 flex gap-2">
            <Button className="min-w-0 flex-1" onClick={submit} disabled={submitting || loading}>
              {t("play.submit")}
            </Button>
            <Button variant="secondary" onClick={clear} disabled={submitting || loading}>
              {t("play.clear")}
            </Button>
          </div>
          <HintCard puzzle={puzzle} usedHints={usedHints} onUse={(id) => setUsedHints((p) => [...p, id])} />
          {error ? <p className="mt-2 text-sm font-bold text-red-600">{error}</p> : null}
        </div>
      ) : (
        <Card className="mt-3">
          <ResultBanner result={result} />
          <FeedbackLegend />
          <p className="mt-3 text-sm font-bold">
            {t("play.correctAnswer")}:{" "}
            <span dir="ltr">{result.detail.correct.concat(result.detail.missed).join("، ") || "—"}</span>
          </p>
          {puzzle.explanation ? (
            <p className="mt-2 text-sm text-stone-600">
              {t("play.explanation")}: {puzzle.explanation}
            </p>
          ) : null}
          <div className="mt-3 flex gap-2">
            <Button className="min-w-0 flex-1" onClick={loadNext} disabled={loading}>
              {t("play.next")}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setResult(null);
                setSelected([]);
                setUsedHints([]);
                setStartedAt(new Date().toISOString());
              }}
            >
              {t("play.retry")}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}

function SpeedLoop() {
  const [session, setSession] = useState<SpeedSummary | null>(null);
  const [puzzle, setPuzzle] = useState<Puzzle | null>(null);
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [summary, setSummary] = useState<SpeedSummary | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>(() => new Date().toISOString());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  // Authoritative clock lives on the server; the visible countdown is only
  // UX. deadlineRef is re-anchored from server remaining_ms on every
  // response, so it never depends on client/server clock agreement.
  const deadlineRef = useRef(0);
  const finishingRef = useRef(false);

  const anchorDeadline = useCallback((remainingMs: number) => {
    deadlineRef.current = Date.now() + Math.max(0, remainingMs);
    setNowMs(Date.now());
  }, []);

  const finish = useCallback(
    async (sessionId: string) => {
      if (finishingRef.current) return;
      finishingRef.current = true;
      try {
        const done = await api.finishSpeedSession(sessionId);
        setSummary(done);
        setSession(done);
      } catch {
        const current = await api.getSpeedSession(sessionId).catch(() => null);
        if (current) {
          setSummary(current);
          setSession(current);
        }
      } finally {
        finishingRef.current = false;
      }
    },
    [],
  );

  const start = useCallback(async () => {
    setBusy(true);
    setError(null);
    setSummary(null);
    setResult(null);
    try {
      const created = await api.startSpeedSession();
      const full: SpeedSummary = {
        ...created,
        attempted: 0,
        correct: 0,
        partial: 0,
        wrong: 0,
        score: 0,
      };
      setSession(full);
      anchorDeadline(created.remaining_ms);
      const first = await api.nextSpeedPuzzle(created.session_id);
      setPuzzle(first);
      setSelected([]);
      setUsedHints([]);
      setStartedAt(new Date().toISOString());
    } catch {
      setError(t("common.error"));
    } finally {
      setBusy(false);
    }
  }, [anchorDeadline]);

  useEffect(() => {
    start();
  }, [start]);

  // Visible countdown; the server still rejects late submits (410).
  useEffect(() => {
    if (!session || summary || session.status !== "active") return;
    const timer = setInterval(() => {
      setNowMs(Date.now());
      if (Date.now() >= deadlineRef.current) {
        clearInterval(timer);
        finish(session.session_id);
      }
    }, 250);
    return () => clearInterval(timer);
  }, [session, summary, finish]);

  const remainingMs = Math.max(0, deadlineRef.current - nowMs);
  const remainingSec = Math.ceil(remainingMs / 1000);

  function toggle(square: string) {
    if (result) return;
    setSelected((prev) => (prev.includes(square) ? prev.filter((s) => s !== square) : [...prev, square]));
  }

  async function submit() {
    if (!session || !puzzle || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.submitSpeedAnswer(session.session_id, {
        puzzle_id: puzzle.id,
        answer: { selected_squares: selected },
        hints_used: usedHints,
        started_at: startedAt,
      });
      setResult(res.attempt);
      setSession(res.session);
      anchorDeadline(res.session.remaining_ms);
    } catch (e) {
      if (e instanceof Error && e.message.includes(":410")) {
        await finish(session.session_id);
        setError(t("speed.expired"));
      } else {
        setError(t("common.error"));
      }
    } finally {
      setBusy(false);
    }
  }

  async function next() {
    if (!session || busy) return;
    if (Date.now() >= deadlineRef.current) {
      await finish(session.session_id);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const nextPuzzle = await api.nextSpeedPuzzle(session.session_id);
      setPuzzle(nextPuzzle);
      setResult(null);
      setSelected([]);
      setUsedHints([]);
      setStartedAt(new Date().toISOString());
    } catch (e) {
      if (e instanceof Error && e.message.includes(":410")) {
        await finish(session.session_id);
      } else {
        setError(t("common.error"));
      }
    } finally {
      setBusy(false);
    }
  }

  if (summary) {
    return (
      <div className="min-w-0">
        <PageHeader title={t("speed.result")} subtitle={t("speed.finished")} />
        <Card>
          <div className="grid grid-cols-2 gap-3 text-center">
            <div className="rounded-2xl bg-violet-50 px-2 py-3">
              <p className="text-2xl font-black text-violet-700">{faNum(summary.attempted)}</p>
              <p className="text-xs text-stone-500">{t("speed.attempted")}</p>
            </div>
            <div className="rounded-2xl bg-amber-50 px-2 py-3">
              <p className="text-2xl font-black text-amber-600">{faNum(Math.round(summary.score * 10) / 10)}</p>
              <p className="text-xs text-stone-500">{t("speed.score")}</p>
            </div>
            <div className="rounded-2xl bg-green-50 px-2 py-3">
              <p className="text-2xl font-black text-green-600">{faNum(summary.correct)}</p>
              <p className="text-xs text-stone-500">{t("play.correctCount")}</p>
            </div>
            <div className="rounded-2xl bg-red-50 px-2 py-3">
              <p className="text-2xl font-black text-red-600">{faNum(summary.wrong)}</p>
              <p className="text-xs text-stone-500">{t("play.wrongCount")}</p>
            </div>
          </div>
          <div className="mt-4 grid gap-2">
            <Button className="w-full" onClick={start}>
              {t("speed.retry")}
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  if (!session || !puzzle) {
    return (
      <Card>
        <p>{error ?? t("common.loading")}</p>
        {error ? (
          <Button className="mt-3" onClick={start}>
            {t("common.retry")}
          </Button>
        ) : null}
      </Card>
    );
  }

  const totalMs = session.duration_s * 1000;
  const progress = Math.max(0, Math.min(1, remainingMs / totalMs));

  return (
    <div className="min-w-0">
      <PageHeader title={t("piece.title")} subtitle={puzzle.prompt_fa} />
      <div
        className="mb-3 rounded-2xl border-2 border-violet-200 bg-white px-4 py-2"
        role="timer"
        aria-live="polite"
        aria-label={t("speed.timeLeft")}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-bold text-stone-600">{t("speed.timeLeft")}</span>
          <span className="text-xl font-black text-violet-700" dir="ltr">
            {faNum(remainingSec)} <span className="text-xs font-bold">{t("common.seconds")}</span>
          </span>
          <Badge>
            {t("play.correctCount")}: {faNum(session.correct)}
          </Badge>
        </div>
        <div className="mt-2 h-2 min-w-0 overflow-hidden rounded-full bg-violet-100" aria-hidden="true">
          <div
            className="h-full rounded-full bg-violet-600 transition-[width]"
            style={{ width: `${Math.round(progress * 100)}%` }}
          />
        </div>
      </div>

      <BoardSection
        puzzle={puzzle}
        selected={selected}
        result={result}
        disabled={result !== null || busy}
        onToggle={toggle}
      />

      {!result ? (
        <div>
          <p className="mt-3 text-sm font-bold text-stone-600">
            {t("play.selected")}: {faNum(selected.length)}
          </p>
          <div className="mt-2 flex gap-2">
            <Button className="min-w-0 flex-1" onClick={submit} disabled={busy}>
              {t("play.submit")}
            </Button>
            <Button variant="secondary" onClick={() => setSelected([])} disabled={busy}>
              {t("play.clear")}
            </Button>
          </div>
          <HintCard puzzle={puzzle} usedHints={usedHints} onUse={(id) => setUsedHints((p) => [...p, id])} />
          {error ? <p className="mt-2 text-sm font-bold text-red-600">{error}</p> : null}
        </div>
      ) : (
        <Card className="mt-3">
          <ResultBanner result={result} />
          <div className="mt-3">
            <Button className="w-full" onClick={next} disabled={busy}>
              {t("play.next")}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
