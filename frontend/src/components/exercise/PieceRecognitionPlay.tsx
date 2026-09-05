import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api/client";
import type { AttemptResponse, Puzzle, SpeedReport, SpeedSummary } from "../../api/types";
import { t } from "../../i18n";
import { fenToPieces } from "../../lib/fen";
import { savePracticeAttempt } from "../../lib/localProgress";
import { ChessBoard } from "../chess/ChessBoard";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FeedbackText, PageHeader } from "../ui/PageHeader";

const faNum = (n: number) => n.toLocaleString("fa-IR");
const faFloat = (n: number) => n.toLocaleString("fa-IR", { maximumFractionDigits: 2 });

export type PieceMode = "practice" | "speed";

// Minimum preloaded speed puzzles before the clock may start (mirrors the
// backend MIN_START_BUFFER). Refill thresholds keep the queue populated.
const MIN_BUFFER = 20;
const REFILL_AT = 8;
const REFILL_COUNT = 10;
// How long speed feedback stays visible before auto-advancing: long enough
// to perceive green/red/orange, short enough to feel instant. No animation
// may extend this; the timer keeps running throughout.
const FEEDBACK_MS = 450;

// Dedicated Practice + Speed loop for Piece Recognition. Renders and
// transports answers only; validation, scoring, and the speed clock stay
// backend-authoritative. Prefetch buffers hold PUBLIC puzzle data only
// (never answers); every submission is graded server-side from scratch.
// The ?mode= URL param (set by the home card's Practice/Speed buttons —
// the buttons ARE the mode selection) picks the loop directly; there is no
// intermediate mode-selection screen.
export function PieceRecognitionPlay({ mode }: { mode: PieceMode }) {
  return mode === "practice" ? <PracticeLoop /> : <SpeedLoop />;
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
      <p className="mt-2 text-center text-lg font-black text-stone-800">
        {faNum(result.score)} {t("speed.score")}
      </p>
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

type PracticePhase = "loading" | "ready" | "submitting" | "feedback" | "error";

function PracticeLoop() {
  const [phase, setPhase] = useState<PracticePhase>("loading");
  const [current, setCurrent] = useState<Puzzle | null>(null);
  const [buffered, setBuffered] = useState<Puzzle | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>("");
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [solved, setSolved] = useState(0);
  const [correctTotal, setCorrectTotal] = useState(0);
  const [scoreTotal, setScoreTotal] = useState(0);
  // Generation counter: stale/slow responses from a previous navigation can
  // never overwrite the current puzzle. Mounted flag guards unmount.
  const genRef = useRef(0);
  const mountedRef = useRef(true);
  const currentIdRef = useRef<number | null>(null);
  const busyRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      genRef.current += 1;
    };
  }, []);

  function alive(gen: number) {
    return mountedRef.current && genRef.current === gen;
  }

  function resetFor(puzzle: Puzzle) {
    currentIdRef.current = puzzle.id;
    setCurrent(puzzle);
    setSelected([]);
    setUsedHints([]);
    setResult(null);
    setError(null);
    setStartedAt(new Date().toISOString());
    setPhase("ready");
  }

  // Prefetch the next puzzle in the background while the user solves the
  // current one. Failures are silent here: advance() falls back to an
  // on-demand fetch, and the current puzzle is never touched.
  async function refill(exclude: number[]) {
    const gen = genRef.current;
    let next: Puzzle | null = null;
    try {
      next = await api.nextPracticePuzzle({ exclude_ids: exclude });
    } catch {
      return;
    }
    if (!alive(gen) || !next || next.id === currentIdRef.current) return;
    setBuffered(next);
  }

  async function loadInitial() {
    const gen = ++genRef.current;
    busyRef.current = false;
    setPhase("loading");
    setError(null);
    let first: Puzzle | null = null;
    try {
      first = await api.nextPracticePuzzle({ exclude_ids: [] });
    } catch {
      first = null;
    }
    if (!alive(gen)) return;
    if (!first) {
      setPhase("error");
      setError(t("common.error"));
      return;
    }
    resetFor(first);
    refill([first.id]);
  }

  useEffect(() => {
    loadInitial();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Swap to the already-prepared puzzle (instant); otherwise fetch on demand.
  function advance() {
    if (busyRef.current) return;
    const gen = ++genRef.current;
    const next = buffered;
    if (next && (!current || next.id !== current.id)) {
      setBuffered(null);
      resetFor(next);
      refill([next.id]);
    } else {
      setBuffered(null);
      setPhase("loading");
      api
        .nextPracticePuzzle({ exclude_ids: current ? [current.id] : [] })
        .then((puzzle) => {
          if (!alive(gen)) return;
          resetFor(puzzle);
          refill([puzzle.id]);
        })
        .catch(() => {
          if (!alive(gen)) return;
          setPhase("error");
          setError(t("common.error"));
        });
    }
  }

  function toggle(square: string) {
    if (phase !== "ready") return;
    setSelected((prev) => (prev.includes(square) ? prev.filter((s) => s !== square) : [...prev, square]));
  }

  async function submit() {
    if (phase !== "ready" || !current || busyRef.current) return;
    busyRef.current = true;
    const gen = genRef.current;
    const puzzleId = current.id;
    const answer = { selected_squares: selected };
    const hints = usedHints;
    const started = startedAt;
    setPhase("submitting");
    setError(null);
    try {
      const res = await api.submitAttempt({
        puzzle_id: puzzleId,
        answer,
        mode: "practice",
        hints_used: hints,
        started_at: started,
      });
      if (!alive(gen)) return;
      setResult(res);
      setSolved((n) => n + 1);
      if (res.result === "correct") setCorrectTotal((n) => n + 1);
      setScoreTotal((s) => s + res.score);
      savePracticeAttempt(puzzleId, res.score);
      setPhase("feedback");
    } catch {
      if (!alive(gen)) return;
      setError(t("common.error"));
      setPhase("ready");
    } finally {
      busyRef.current = false;
    }
  }

  function retryCurrent() {
    if (!current || busyRef.current) return;
    setSelected([]);
    setUsedHints([]);
    setResult(null);
    setError(null);
    setStartedAt(new Date().toISOString());
    setPhase("ready");
  }

  if (phase === "loading" && !current) return <p>{t("common.loading")}</p>;
  if ((phase === "error" || !current) && !current) {
    return (
      <Card>
        <p>{error ?? t("common.error")}</p>
        <Button className="mt-3" onClick={loadInitial}>
          {t("common.retry")}
        </Button>
      </Card>
    );
  }
  const puzzle = current;
  if (!puzzle) return <p>{t("common.loading")}</p>;
  const answering = phase === "ready" || phase === "submitting";

  return (
    <div className="min-w-0">
      <PageHeader title={t("piece.title")} subtitle={puzzle.prompt_fa} />
      <div className="mb-3 flex min-w-0 flex-wrap items-center gap-2">
        <Badge>{t("play.practice")}</Badge>
        <Badge>
          {t("practice.solved")}: {faNum(solved)} · {t("play.correctCount")}: {faNum(correctTotal)} ·{" "}
          {t("speed.score")}: {faNum(scoreTotal)}
        </Badge>
      </div>

      <BoardSection
        puzzle={puzzle}
        selected={selected}
        result={result}
        disabled={!answering}
        onToggle={toggle}
      />

      {phase !== "feedback" ? (
        <div>
          <p className="mt-3 text-sm font-bold text-stone-600">
            {t("play.selected")}: {faNum(selected.length)}
          </p>
          <p className="mt-1 text-xs text-stone-500">{t("piece.emptyAllowed")}</p>
          <div className="mt-2 flex gap-2">
            <Button className="min-w-0 flex-1" onClick={submit} disabled={phase !== "ready"}>
              {t("play.submit")}
            </Button>
            <Button variant="secondary" onClick={() => setSelected([])} disabled={phase !== "ready"}>
              {t("play.clear")}
            </Button>
          </div>
          <HintCard puzzle={puzzle} usedHints={usedHints} onUse={(id) => setUsedHints((p) => [...p, id])} />
          {error ? <p className="mt-2 text-sm font-bold text-red-600">{error}</p> : null}
        </div>
      ) : (
        result && (
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
              <Button className="min-w-0 flex-1" onClick={advance}>
                {t("play.next")}
              </Button>
              <Button variant="secondary" onClick={retryCurrent}>
                {t("play.retry")}
              </Button>
            </div>
          </Card>
        )
      )}
    </div>
  );
}

type SpeedPhase = "preparing" | "active" | "report";

function SpeedLoop() {
  const [phase, setPhase] = useState<SpeedPhase>("preparing");
  const [session, setSession] = useState<SpeedSummary | null>(null);
  // Upcoming puzzles (current is tracked separately in currentRef). The ref
  // is the source of truth for async logic; queueTick re-renders on change.
  const [, setQueueTick] = useState(0);
  const [current, setCurrent] = useState<Puzzle | null>(null);
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [report, setReport] = useState<SpeedReport | null>(null);
  const [prepared, setPrepared] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  // Authoritative clock lives on the server; the visible countdown is only
  // UX. deadlineRef is re-anchored from server remaining_ms on every
  // response, so it never depends on client/server clock agreement.
  const deadlineRef = useRef(0);
  const finishingRef = useRef(false);
  const refillingRef = useRef(false);
  const busyRef = useRef(false);
  // Pending auto-advance after speed feedback. Cancelled on expiry, boot,
  // or unmount so a stale timer can never change the puzzle or double-advance.
  const transitionRef = useRef<number | null>(null);
  const genRef = useRef(0);
  const mountedRef = useRef(true);
  const sessionIdRef = useRef<string | null>(null);
  const queueRef = useRef<Puzzle[]>([]);
  const currentRef = useRef<Puzzle | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      genRef.current += 1;
      if (transitionRef.current !== null) {
        clearTimeout(transitionRef.current);
        transitionRef.current = null;
      }
      // Best-effort: close an open session when navigating away so its
      // summary/report stays available instead of lingering half-open.
      const sid = sessionIdRef.current;
      if (sid) api.finishSpeedSession(sid).catch(() => null);
    };
  }, []);

  function alive(gen: number) {
    return mountedRef.current && genRef.current === gen;
  }

  function cancelTransition() {
    if (transitionRef.current !== null) {
      clearTimeout(transitionRef.current);
      transitionRef.current = null;
    }
  }

  function anchorDeadline(remainingMs: number) {
    deadlineRef.current = Date.now() + Math.max(0, remainingMs);
    setNowMs(Date.now());
  }

  function isGone(e: unknown) {
    return e instanceof Error && e.message.includes(":410");
  }

  function resetFor(puzzle: Puzzle) {
    currentRef.current = puzzle;
    setCurrent(puzzle);
    setSelected([]);
    setUsedHints([]);
    setResult(null);
    setError(null);
    setStartedAt(new Date().toISOString());
  }

  async function finishToReport(sessionId: string, gen: number) {
    if (finishingRef.current) return;
    finishingRef.current = true;
    cancelTransition();
    try {
      await api.finishSpeedSession(sessionId).catch(() => null);
      const data = await api.getSpeedReport(sessionId);
      if (!alive(gen) || sessionIdRef.current !== sessionId) return;
      setReport(data);
      setSession(data.session);
      anchorDeadline(0);
      setPhase("report");
    } catch {
      if (!alive(gen)) return;
      setError(t("common.error"));
    } finally {
      finishingRef.current = false;
    }
  }

  // Open session -> prepare >=20 -> start clock. The clock starts only
  // after the buffer is ready; preparation time is never billed.
  async function boot() {
    const gen = ++genRef.current;
    busyRef.current = false;
    refillingRef.current = false;
    finishingRef.current = false;
    cancelTransition();
    const prev = sessionIdRef.current;
    sessionIdRef.current = null;
    queueRef.current = [];
    currentRef.current = null;
    setQueueTick((n) => n + 1);
    setCurrent(null);
    setResult(null);
    setReport(null);
    setPrepared(0);
    setError(null);
    setPhase("preparing");
    try {
      if (prev) await api.finishSpeedSession(prev).catch(() => null);
      const created = await api.startSpeedSession();
      if (!alive(gen)) return;
      sessionIdRef.current = created.session_id;
      setSession({
        ...created,
        attempted: 0,
        correct: 0,
        partial: 0,
        wrong: 0,
        score: 0,
      });
      const acc: Puzzle[] = [];
      let guard = 0;
      while (acc.length < MIN_BUFFER && guard < 6) {
        guard += 1;
        const batch = await api.prepareSpeedPuzzles(created.session_id, { count: MIN_BUFFER });
        if (!alive(gen) || sessionIdRef.current !== created.session_id) return;
        for (const p of batch) {
          if (!acc.some((q) => q.id === p.id)) acc.push(p);
        }
        setPrepared(acc.length);
      }
      if (acc.length < MIN_BUFFER) throw new Error("buffer_not_ready");
      const started = await api.startSpeedClock(created.session_id);
      if (!alive(gen) || sessionIdRef.current !== created.session_id) return;
      setSession({
        ...started,
        attempted: 0,
        correct: 0,
        partial: 0,
        wrong: 0,
        score: 0,
      });
      anchorDeadline(started.remaining_ms);
      queueRef.current = acc.slice(1);
      setQueueTick((n) => n + 1);
      resetFor(acc[0]);
      setPhase("active");
    } catch {
      if (!alive(gen)) return;
      sessionIdRef.current = null;
      setError(t("common.error"));
    }
  }

  useEffect(() => {
    boot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Background refill: keep the queue populated while the user solves.
  // Failures are silent (the current puzzle is unaffected); exhaustion is
  // handled by advance()'s single-fetch fallback.
  async function refillIfNeeded() {
    const sid = sessionIdRef.current;
    const gen = genRef.current;
    if (!sid || refillingRef.current) return;
    if (queueRef.current.length >= REFILL_AT) return;
    refillingRef.current = true;
    try {
      const batch = await api.prepareSpeedPuzzles(sid, { count: REFILL_COUNT });
      if (!alive(gen) || sessionIdRef.current !== sid) return;
      const ids = new Set(queueRef.current.map((p) => p.id));
      if (currentRef.current) ids.add(currentRef.current.id);
      const fresh = batch.filter((p) => !ids.has(p.id));
      if (fresh.length > 0) {
        queueRef.current = [...queueRef.current, ...fresh];
        setQueueTick((n) => n + 1);
      }
    } catch (e) {
      if (isGone(e)) await finishToReport(sid, gen);
    } finally {
      refillingRef.current = false;
    }
  }

  // Visible countdown; the server still rejects late submits (410).
  useEffect(() => {
    if (phase !== "active" || !session || session.status !== "active") return;
    const sid = session.session_id;
    const gen = genRef.current;
    const timer = setInterval(() => {
      setNowMs(Date.now());
      if (Date.now() >= deadlineRef.current) {
        clearInterval(timer);
        finishToReport(sid, gen);
      }
    }, 250);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, session]);

  const remainingMs = Math.max(0, deadlineRef.current - nowMs);
  const remainingSec = Math.ceil(remainingMs / 1000);

  function toggle(square: string) {
    if (phase !== "active" || result) return;
    setSelected((prev) => (prev.includes(square) ? prev.filter((s) => s !== square) : [...prev, square]));
  }

  async function submit() {
    const puzzle = currentRef.current;
    const sid = sessionIdRef.current;
    // Single lock held from submit through the feedback window until the
    // auto-advance completes: no double-submit, no interaction mid-transition.
    if (phase !== "active" || !puzzle || !sid || busyRef.current) return;
    busyRef.current = true;
    const gen = genRef.current;
    setBusy(true);
    setError(null);
    try {
      const res = await api.submitSpeedAnswer(sid, {
        puzzle_id: puzzle.id,
        answer: { selected_squares: selected },
        hints_used: usedHints,
        started_at: startedAt,
      });
      if (!alive(gen) || sessionIdRef.current !== sid) {
        busyRef.current = false;
        return;
      }
      setResult(res.attempt);
      setSession(res.session);
      anchorDeadline(res.session.remaining_ms);
      // Briefly show green/red/orange on the board, then advance with NO
      // manual button. The timer keeps running; expiry cancels this.
      transitionRef.current = window.setTimeout(() => {
        transitionRef.current = null;
        if (!alive(gen) || sessionIdRef.current !== sid) {
          busyRef.current = false;
          return;
        }
        advance();
      }, FEEDBACK_MS);
    } catch (e) {
      if (!alive(gen)) {
        busyRef.current = false;
        return;
      }
      if (isGone(e)) {
        busyRef.current = false;
        if (alive(gen)) setBusy(false);
        await finishToReport(sid, gen);
        setError(t("speed.expired"));
      } else {
        busyRef.current = false;
        setError(t("common.error"));
        if (alive(gen)) setBusy(false);
      }
    }
  }

  // Auto-advance only (called by the feedback timer). Releases the submit
  // lock when done; expiry during the window routes to the report instead.
  async function advance() {
    const sid = sessionIdRef.current;
    if (phase !== "active" || !sid) {
      busyRef.current = false;
      return;
    }
    if (Date.now() >= deadlineRef.current) {
      busyRef.current = false;
      if (alive(genRef.current)) setBusy(false);
      await finishToReport(sid, genRef.current);
      return;
    }
    const [next, ...rest] = queueRef.current;
    if (next) {
      queueRef.current = rest;
      setQueueTick((n) => n + 1);
      resetFor(next);
      refillIfNeeded();
      return;
    }
    // Queue exhausted (shouldn't happen under normal conditions): single
    // on-demand fetch instead of a dead end.
    busyRef.current = true;
    setBusy(true);
    setError(null);
    try {
      const puzzle = await api.nextSpeedPuzzle(sid);
      const gen = genRef.current;
      if (!alive(gen) || sessionIdRef.current !== sid) return;
      resetFor(puzzle);
      refillIfNeeded();
    } catch (e) {
      const gen = genRef.current;
      if (!alive(gen)) return;
      if (isGone(e)) await finishToReport(sid, gen);
      else setError(t("common.error"));
    } finally {
      busyRef.current = false;
      if (alive(genRef.current)) setBusy(false);
    }
  }

  if (phase === "preparing") {
    return (
      <div className="min-w-0">
        <PageHeader title={t("piece.title")} subtitle={t("speed.howto")} />
        <Card>
          <p className="text-center text-sm font-bold text-stone-600">{t("speed.preparing")}</p>
          <p className="mt-2 text-center text-2xl font-black text-violet-700" dir="ltr">
            {faNum(Math.min(prepared, MIN_BUFFER))} / {faNum(MIN_BUFFER)}
          </p>
          <div className="mt-3 h-2 min-w-0 overflow-hidden rounded-full bg-violet-100" aria-hidden="true">
            <div
              className="h-full rounded-full bg-violet-600 transition-[width]"
              style={{ width: `${Math.round((Math.min(prepared, MIN_BUFFER) / MIN_BUFFER) * 100)}%` }}
            />
          </div>
          {error ? (
            <div>
              <p className="mt-3 text-center text-sm font-bold text-red-600">{error}</p>
              <Button className="mt-3 w-full" onClick={boot}>
                {t("common.retry")}
              </Button>
            </div>
          ) : null}
        </Card>
      </div>
    );
  }

  if (phase === "report") {
    return <SpeedReportView report={report} error={error} onRetry={boot} />;
  }

  const puzzle = current;
  if (!session || !puzzle) {
    return (
      <Card>
        <p>{error ?? t("common.loading")}</p>
        {error ? (
          <Button className="mt-3" onClick={boot}>
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
        <div className="flex min-w-0 items-center justify-between gap-2">
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
          <p className="mt-1 text-xs text-stone-500">{t("piece.emptyAllowed")}</p>
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
        // Speed feedback is transient: green/red/orange stay on the board
        // for FEEDBACK_MS, then the loop auto-advances. No manual button.
        <Card className="mt-3">
          <ResultBanner result={result} />
        </Card>
      )}
    </div>
  );
}

function resultLabel(result: string) {
  if (result === "correct") return t("report.correct");
  if (result === "partial") return t("report.partial");
  return t("report.wrong");
}

function SpeedReportView({
  report,
  error,
  onRetry,
}: {
  report: SpeedReport | null;
  error: string | null;
  onRetry: () => void;
}) {
  if (!report) {
    return (
      <Card>
        <p>{error ?? t("common.loading")}</p>
        {error ? (
          <Button className="mt-3" onClick={onRetry}>
            {t("common.retry")}
          </Button>
        ) : null}
      </Card>
    );
  }
  const { session, entries } = report;
  const average = session.attempted > 0 ? session.score / session.attempted : null;
  const accuracy = session.attempted > 0 ? Math.round((session.correct / session.attempted) * 100) : null;
  return (
    <div className="min-w-0">
      <PageHeader title={t("speed.result")} subtitle={t("speed.finished")} />
      <Card>
        {session.attempted === 0 ? (
          <p className="text-center text-sm font-bold text-stone-600">{t("report.empty")}</p>
        ) : (
          <div className="grid grid-cols-2 gap-2 text-center sm:grid-cols-3">
            <div className="rounded-2xl bg-violet-50 px-2 py-3">
              <p className="text-2xl font-black text-violet-700">{faNum(session.attempted)}</p>
              <p className="text-xs text-stone-500">{t("speed.attempted")}</p>
            </div>
            <div className="rounded-2xl bg-green-50 px-2 py-3">
              <p className="text-2xl font-black text-green-600">{faNum(session.correct)}</p>
              <p className="text-xs text-stone-500">{t("report.correct")}</p>
            </div>
            <div className="rounded-2xl bg-amber-50 px-2 py-3">
              <p className="text-2xl font-black text-amber-600">{faNum(session.partial)}</p>
              <p className="text-xs text-stone-500">{t("report.partial")}</p>
            </div>
            <div className="rounded-2xl bg-red-50 px-2 py-3">
              <p className="text-2xl font-black text-red-600">{faNum(session.wrong)}</p>
              <p className="text-xs text-stone-500">{t("report.wrong")}</p>
            </div>
            <div className="rounded-2xl bg-violet-50 px-2 py-3">
              <p className="text-2xl font-black text-violet-700">{faNum(session.score)}</p>
              <p className="text-xs text-stone-500">{t("speed.score")}</p>
            </div>
            <div className="rounded-2xl bg-stone-100 px-2 py-3">
              <p className="text-2xl font-black text-stone-700">
                {average === null ? "—" : faFloat(average)}
              </p>
              <p className="text-xs text-stone-500">{t("speed.average")}</p>
            </div>
          </div>
        )}
        {accuracy !== null ? (
          <p className="mt-3 text-center text-sm font-bold text-stone-600">
            {t("speed.accuracy")}: <span dir="ltr">{faNum(accuracy)}٪</span>
          </p>
        ) : null}
        {entries.length > 0 ? (
          <ul className="mt-4 grid gap-2">
            {entries.map((entry, index) => {
              const tone =
                entry.result === "correct"
                  ? "border-green-500 bg-green-50"
                  : entry.result === "partial"
                    ? "border-amber-500 bg-amber-50"
                    : "border-red-400 bg-red-50";
              return (
                <li key={entry.attempt_id} className={`rounded-2xl border-2 px-4 py-3 ${tone}`}>
                  <div className="flex min-w-0 items-center justify-between gap-2">
                    <p className="min-w-0 truncate text-sm font-black text-stone-800">
                      {t("report.puzzle")} {faNum(index + 1)} · {entry.prompt_fa}
                    </p>
                    <span className="shrink-0 text-sm font-black">{resultLabel(entry.result)}</span>
                  </div>
                  <p className="mt-1 text-sm font-bold text-stone-700">
                    {faNum(entry.score)} {t("speed.score")} · {t("play.missedCount")}:{" "}
                    {faNum(entry.missed.length)} · {t("play.wrongCount")}: {faNum(entry.wrong.length)}
                  </p>
                  <p className="mt-1 text-xs text-stone-500">
                    {t("play.correctAnswer")}:{" "}
                    <span dir="ltr">{entry.correct.concat(entry.missed).join("، ") || "—"}</span>
                  </p>
                </li>
              );
            })}
          </ul>
        ) : null}
        <div className="mt-4 grid gap-2">
          <Button className="w-full" onClick={onRetry}>
            {t("speed.retry")}
          </Button>
        </div>
      </Card>
    </div>
  );
}

