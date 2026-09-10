import { useEffect, useRef, useState } from "react";
import { api, apiDetail, apiStatus } from "../../api/client";
import type { AttemptResponse, Puzzle, SpeedReport, SpeedSummary } from "../../api/types";
import { t } from "../../i18n";
import { savePracticeAttempt } from "../../lib/localProgress";
import { playError, playSuccess } from "../../lib/sound";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FeedbackText } from "../ui/PageHeader";
import {
  BoardZone,
  GameShell,
  NextBar,
  QuestionHeader,
  TimerStrip,
  faNum,
  useGameFit,
} from "./PieceGameLayout";

export type SquareVisionMode = "practice" | "speed";

export const SQUARE_VISION_CHOICES = ["white", "black"] as const;
export type SquareVisionChoice = (typeof SQUARE_VISION_CHOICES)[number];

// Dedicated Practice + Speed loop for Blindfold Square Vision
// (خانه‌یابی ذهنی): one uniform-random square per puzzle, name its color.
// Practice shows an empty tappable board (tap the asked square; correct =
// green, wrong tap = red, missed target = orange). Speed shows no board:
// two large سفید/سیاه buttons, only the tapped one colorizes. Renders and
// transports answers only; the color verdict, scoring (+5/−3), and the
// speed clock stay backend-authoritative. Prefetch buffers hold PUBLIC
// puzzle data only (the square is the question; its color never leaves
// the server). The ?mode= URL param (set by the home card's
// Practice/Speed buttons — the buttons ARE the mode selection) picks the
// loop directly; there is no intermediate mode-selection screen.
//
// Layout: full-viewport game shell (no page scroll). Portrait stacks
// question → board/choices; landscape puts the board beside a control
// column. The practice board is exactly fitted to its area.
export function BlindfoldSquareVisionPlay({ mode }: { mode: SquareVisionMode }) {
  return mode === "practice" ? <PracticeLoop /> : <SpeedLoop />;
}

export function choiceLabel(id: string): string {
  if (id === "white") return t("blindfold.white");
  if (id === "black") return t("blindfold.black");
  return id;
}

function SquareButtons({
  disabled,
  selected,
  result,
  onChoose,
}: {
  disabled: boolean;
  selected: string | null;
  result: AttemptResponse | null;
  onChoose: (choice: SquareVisionChoice) => void;
}) {
  return (
    <div className="grid shrink-0 gap-2 px-3 pt-1" role="group" aria-label={t("blindfold.intro")}>
      {SQUARE_VISION_CHOICES.map((choice) => {
        const isSelected = selected === choice;
        // Only the tapped answer colorizes: green when it was correct,
        // red when it was not. The other button never changes.
        const state = result && isSelected ? (result.result === "correct" ? "correct" : "wrong") : isSelected ? "active" : "idle";
        const styles: Record<string, string> = {
          correct: "border-green-500 bg-green-50 text-green-800",
          wrong: "border-red-400 bg-red-50 text-red-700",
          active: "border-violet-600 bg-violet-50 text-violet-800",
          idle: "border-stone-200 bg-white text-stone-700",
        };
        return (
          <button
            key={choice}
            type="button"
            aria-pressed={isSelected}
            disabled={disabled}
            onClick={() => onChoose(choice)}
            className={`flex min-h-[64px] items-center justify-center rounded-2xl border-2 px-4 py-3 text-xl font-black transition ${styles[state]}`}
            style={{ touchAction: "manipulation" }}
          >
            {choiceLabel(choice)}
          </button>
        );
      })}
    </div>
  );
}

function AnswerFeedback({ result }: { result: AttemptResponse }) {
  const isCorrect = result.result === "correct";
  const tone = isCorrect ? "border-green-500 bg-green-50" : "border-red-400 bg-red-50";
  return (
    <div className="shrink-0 px-3" data-testid="feedback">
      <div className={`rounded-2xl border-2 px-3 py-2 text-center ${tone}`}>
        <FeedbackText feedbackKey={result.feedback_key} />
        <p className="mt-1 text-base font-black text-stone-800">
          {faNum(result.score)} {t("speed.score")}
        </p>
      </div>
    </div>
  );
}

type PracticePhase = "loading" | "ready" | "submitting" | "feedback" | "error";

// How long practice feedback stays visible before auto-advancing: long
// enough to read green/red/orange on the board, short enough to keep
// momentum. A manual «next» button is also shown (family convention).
const PRACTICE_FEEDBACK_MS = 1000;

function PracticeLoop() {
  const [phase, setPhase] = useState<PracticePhase>("loading");
  const [current, setCurrent] = useState<Puzzle | null>(null);
  const [buffered, setBuffered] = useState<Puzzle | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
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
  // Pending practice auto-advance. Cancelled on manual next, retry, or
  // unmount so a stale timer can never skip a puzzle.
  const transitionRef = useRef<number | null>(null);
  const { rootRef, areaRef, orientation, size } = useGameFit();

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      genRef.current += 1;
      if (transitionRef.current !== null) {
        clearTimeout(transitionRef.current);
        transitionRef.current = null;
      }
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

  function resetFor(puzzle: Puzzle) {
    cancelTransition();
    currentIdRef.current = puzzle.id;
    setCurrent(puzzle);
    setSelected(null);
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
      next = await api.nextSquareVisionPracticePuzzle({ exclude_ids: exclude });
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
      first = await api.nextSquareVisionPracticePuzzle({ exclude_ids: [] });
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
    cancelTransition();
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
        .nextSquareVisionPracticePuzzle({ exclude_ids: current ? [current.id] : [] })
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

  // Immediate tap → validation → feedback → auto-advance. No separate
  // Submit button: tapping a square submits it.
  async function choose(square: string) {
    if (phase !== "ready" || !current || busyRef.current) return;
    busyRef.current = true;
    const gen = genRef.current;
    const puzzleId = current.id;
    const started = startedAt;
    setSelected(square);
    setPhase("submitting");
    setError(null);
    try {
      const res = await api.submitAttempt({
        puzzle_id: puzzleId,
        answer: { square },
        mode: "practice",
        hints_used: [],
        started_at: started,
      });
      if (!alive(gen)) return;
      setResult(res);
      setSolved((n) => n + 1);
      if (res.result === "correct") {
        setCorrectTotal((n) => n + 1);
        playSuccess();
      } else {
        playError();
      }
      setScoreTotal((s) => s + res.score);
      savePracticeAttempt(puzzleId, res.score);
      setPhase("feedback");
      // Auto-advance after the feedback window (manual next cancels it).
      transitionRef.current = window.setTimeout(() => {
        transitionRef.current = null;
        if (!alive(gen)) return;
        advance();
      }, PRACTICE_FEEDBACK_MS);
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
    cancelTransition();
    setSelected(null);
    setResult(null);
    setError(null);
    setStartedAt(new Date().toISOString());
    setPhase("ready");
  }

  const stat = `${faNum(solved)} · ${faNum(correctTotal)} · ${faNum(scoreTotal)}`;
  if ((phase === "loading" || phase === "error") && !current) {
    return (
      <GameShell title={t("exercises.blindfold-square-vision.title")} modeKey="play.practice">
        <div className="grid min-h-0 flex-1 place-items-center px-4">
          <Card>
            <p className="text-center">{phase === "error" ? (error ?? t("common.error")) : t("common.loading")}</p>
            {phase === "error" ? (
              <Button className="mt-3 w-full" onClick={loadInitial}>
                {t("common.retry")}
              </Button>
            ) : null}
          </Card>
        </div>
      </GameShell>
    );
  }
  const puzzle = current;
  if (!puzzle) {
    return (
      <GameShell title={t("exercises.blindfold-square-vision.title")} modeKey="play.practice">
        <div className="grid min-h-0 flex-1 place-items-center px-4">
          <p>{t("common.loading")}</p>
        </div>
      </GameShell>
    );
  }
  const answering = phase === "ready";
  const action =
    phase === "feedback" ? (
      <div className="shrink-0 px-3 pb-3 pt-1" data-testid="next-bar">
        <NextBar onNext={advance} onRetry={retryCurrent} />
      </div>
    ) : null;
  const feedback = phase === "feedback" && result ? <AnswerFeedback result={result} /> : null;
  const question = <QuestionHeader prompt={puzzle.prompt_fa} puzzleKey={puzzle.id} hints={[]} usedHints={[]} onUseHint={() => null} />;
  // Empty tappable board: the asked square's color is the question. Board
  // feedback comes from the server detail (correct=green, missed=orange,
  // wrong=red) via the shared BoardZone mapping — no local coloring.
  const board = (
    <BoardZone
      areaRef={areaRef}
      size={size}
      puzzle={puzzle}
      selected={selected ? [selected] : []}
      result={result}
      disabled={!answering}
      onToggle={choose}
    />
  );

  return (
    <GameShell title={t("exercises.blindfold-square-vision.title")} modeKey="play.practice" stat={stat}>
      <div ref={rootRef} className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {orientation === "landscape" ? (
          <div className="flex min-h-0 min-w-0 flex-1">
            {board}
            <aside className="flex w-60 shrink-0 flex-col gap-1 overflow-y-auto py-1">
              {question}
              {feedback}
              {action}
            </aside>
          </div>
        ) : (
          <>
            {question}
            {board}
            {feedback}
            {action}
          </>
        )}
      </div>
    </GameShell>
  );
}

type SpeedPhase = "preparing" | "active" | "report";

// Minimum preloaded speed puzzles before the clock may start (mirrors the
// backend MIN_START_BUFFER). Refill thresholds keep the queue populated.
const MIN_BUFFER = 20;
// Refill early (well above zero) with a generous batch, so normal play
// never waits: the buffer oscillates in a healthy range instead of
// repeatedly draining toward empty.
const REFILL_AT = 12;
const REFILL_COUNT = 12;
// Consecutive backend-unknown puzzles before the session is declared lost.
const MAX_SKIPS = 3;
// How long speed feedback stays visible before auto-advancing: long enough
// to perceive green/red, short enough to feel instant. No animation
// may extend this; the timer keeps running throughout.
const FEEDBACK_MS = 450;

function SpeedLoop() {
  const [phase, setPhase] = useState<SpeedPhase>("preparing");
  const [session, setSession] = useState<SpeedSummary | null>(null);
  // Upcoming puzzles (current is tracked separately in currentRef). The ref
  // is the source of truth for async logic; queueTick re-renders on change.
  const [, setQueueTick] = useState(0);
  const [current, setCurrent] = useState<Puzzle | null>(null);
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [report, setReport] = useState<SpeedReport | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
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
  // Consecutive ungradeable puzzles (unknown to the backend, e.g. after a
  // server data reset). After MAX_SKIPS the session is declared lost instead
  // of draining the whole queue one 404 at a time.
  const consecutiveSkipRef = useRef(0);
  // False once the backend confirms the session is gone: skips the
  // best-effort finish call on unmount (it would 404 too).
  const sessionAliveRef = useRef(true);
  const genRef = useRef(0);
  const mountedRef = useRef(true);
  const sessionIdRef = useRef<string | null>(null);
  const queueRef = useRef<Puzzle[]>([]);
  const currentRef = useRef<Puzzle | null>(null);
  const { rootRef } = useGameFit();

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
      // Skipped when the backend already confirmed the session is gone.
      const sid = sessionIdRef.current;
      if (sid && sessionAliveRef.current) api.finishSquareVisionSpeedSession(sid).catch(() => null);
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
    return apiStatus(e) === 410;
  }

  function isSessionLost(e: unknown) {
    return apiStatus(e) === 404 && (apiDetail(e) === "session_not_found" || apiDetail(e) === "session_expired");
  }

  function isUnknownPuzzle(e: unknown) {
    return (
      apiStatus(e) === 404 &&
      (apiDetail(e) === "puzzle_not_in_session" || apiDetail(e) === "puzzle_not_available")
    );
  }

  // Unrecoverable session loss (e.g. backend data was reset mid-run):
  // recover the authoritative report when possible, otherwise land on the
  // dead screen (error + retry → fresh boot). Never leaves the user stuck
  // on a puzzle that can never be graded.
  async function dieToReport(sessionId: string, gen: number) {
    sessionAliveRef.current = false;
    busyRef.current = false;
    if (alive(gen)) setBusy(false);
    try {
      const data = await api.getSquareVisionSpeedReport(sessionId);
      if (!alive(gen) || sessionIdRef.current !== sessionId) return;
      setReport(data);
      setSession(data.session);
      anchorDeadline(0);
      setError(null);
      setPhase("report");
    } catch {
      if (!alive(gen)) return;
      setReport(null);
      setSession(null);
      setError(t("speed.sessionLost"));
      setPhase("report");
    }
  }

  function resetFor(puzzle: Puzzle) {
    currentRef.current = puzzle;
    setCurrent(puzzle);
    setSelected(null);
    setResult(null);
    setError(null);
    setStartedAt(new Date().toISOString());
  }

  async function finishToReport(sessionId: string, gen: number) {
    if (finishingRef.current) return;
    finishingRef.current = true;
    cancelTransition();
    try {
      await api.finishSquareVisionSpeedSession(sessionId).catch(() => null);
      const data = await api.getSquareVisionSpeedReport(sessionId);
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
    consecutiveSkipRef.current = 0;
    sessionAliveRef.current = true;
    cancelTransition();
    const prev = sessionIdRef.current;
    sessionIdRef.current = null;
    queueRef.current = [];
    currentRef.current = null;
    setQueueTick((n) => n + 1);
    setCurrent(null);
    setResult(null);
    setReport(null);
    setError(null);
    setPhase("preparing");
    try {
      if (prev) await api.finishSquareVisionSpeedSession(prev).catch(() => null);
      const created = await api.startSquareVisionSpeedSession();
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
        const batch = await api.prepareSquareVisionSpeedPuzzles(created.session_id, { count: MIN_BUFFER });
        if (!alive(gen) || sessionIdRef.current !== created.session_id) return;
        for (const p of batch) {
          if (!acc.some((q) => q.id === p.id)) acc.push(p);
        }
      }
      if (acc.length < MIN_BUFFER) throw new Error("buffer_not_ready");
      const started = await api.startSquareVisionSpeedClock(created.session_id);
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
      const batch = await api.prepareSquareVisionSpeedPuzzles(sid, { count: REFILL_COUNT });
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

  async function choose(choice: SquareVisionChoice) {
    const puzzle = currentRef.current;
    const sid = sessionIdRef.current;
    // Single lock held from submit through the feedback window until the
    // auto-advance completes: no double-submit, no interaction mid-transition.
    if (phase !== "active" || !puzzle || !sid || busyRef.current) return;
    busyRef.current = true;
    const gen = genRef.current;
    setBusy(true);
    setSelected(choice);
    setError(null);
    try {
      const res = await api.submitSquareVisionSpeedAnswer(sid, {
        puzzle_id: puzzle.id,
        answer: { choice },
        hints_used: [],
        started_at: startedAt,
      });
      if (!alive(gen) || sessionIdRef.current !== sid) {
        busyRef.current = false;
        return;
      }
      setResult(res.attempt);
      if (res.attempt.result === "correct") playSuccess();
      else playError();
      setSession(res.session);
      consecutiveSkipRef.current = 0;
      anchorDeadline(res.session.remaining_ms);
      // Briefly show green/red on the tapped button, then advance with NO
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
      } else if (isSessionLost(e)) {
        // Backend no longer knows this session (e.g. server data was reset
        // mid-run): recover the report when possible, else the dead screen
        // with a fresh-start retry. Never loop the same 404.
        await dieToReport(sid, gen);
      } else if (isUnknownPuzzle(e)) {
        // Current puzzle can't be graded, but the session may be fine:
        // drop it and move on; give up after repeated failures.
        consecutiveSkipRef.current += 1;
        if (consecutiveSkipRef.current >= MAX_SKIPS) {
          await dieToReport(sid, gen);
        } else {
          busyRef.current = false;
          if (alive(gen)) setBusy(false);
          advance();
        }
      } else {
        busyRef.current = false;
        setError(t("common.error"));
        if (alive(gen)) setBusy(false);
      }
    }
  }

  // Auto-advance only (called by the feedback timer). Releases the submit
  // lock on EVERY path — including the instant queued swap — so the next
  // puzzle is always submittable. Expiry during the window routes to the
  // report instead.
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
      busyRef.current = false;
      if (alive(genRef.current)) setBusy(false);
      refillIfNeeded();
      return;
    }
    // Queue exhausted (shouldn't happen under normal conditions): single
    // on-demand fetch instead of a dead end.
    busyRef.current = true;
    setBusy(true);
    setError(null);
    try {
      const puzzle = await api.nextSquareVisionSpeedPuzzle(sid);
      const gen = genRef.current;
      if (!alive(gen) || sessionIdRef.current !== sid) return;
      resetFor(puzzle);
      refillIfNeeded();
    } catch (e) {
      const gen = genRef.current;
      if (!alive(gen)) return;
      if (isGone(e)) await finishToReport(sid, gen);
      else if (isSessionLost(e)) await dieToReport(sid, gen);
      else if (isUnknownPuzzle(e)) {
        consecutiveSkipRef.current += 1;
        if (consecutiveSkipRef.current >= MAX_SKIPS) await dieToReport(sid, gen);
        else setError(t("common.error"));
      } else setError(t("common.error"));
    } finally {
      busyRef.current = false;
      if (alive(genRef.current)) setBusy(false);
    }
  }

  if (phase === "preparing") {
    // Deliberately simple: internal buffer counts are never shown to users.
    return (
      <GameShell title={t("exercises.blindfold-square-vision.title")} modeKey="play.speed">
        <div className="grid min-h-0 flex-1 place-items-center px-4">
          <Card>
            <p className="text-center text-sm font-bold text-stone-600">{t("speed.preparing")}</p>
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
      </GameShell>
    );
  }

  if (phase === "report") {
    return <SpeedReportView report={report} error={error} onRetry={boot} />;
  }

  const puzzle = current;
  if (!session || !puzzle) {
    return (
      <GameShell title={t("exercises.blindfold-square-vision.title")} modeKey="play.speed">
        <div className="grid min-h-0 flex-1 place-items-center px-4">
          <Card>
            <p className="text-center">{error ?? t("common.loading")}</p>
            {error ? (
              <Button className="mt-3 w-full" onClick={boot}>
                {t("common.retry")}
              </Button>
            ) : null}
          </Card>
        </div>
      </GameShell>
    );
  }

  const totalMs = session.duration_s * 1000;
  const progress = Math.max(0, Math.min(1, remainingMs / totalMs));
  const timer = (
    <TimerStrip remainingSec={remainingSec} correct={session.correct} progress={progress} />
  );
  const question = (
    <QuestionHeader prompt={puzzle.prompt_fa} puzzleKey={puzzle.id} hints={[]} usedHints={[]} onUseHint={() => null} />
  );
  const choices = (
    <SquareButtons
      disabled={result !== null || busy}
      selected={selected}
      result={result}
      onChoose={choose}
    />
  );

  return (
    <GameShell title={t("exercises.blindfold-square-vision.title")} modeKey="play.speed">
      <div ref={rootRef} className="flex min-h-0 min-w-0 flex-1 flex-col justify-center gap-1 overflow-hidden px-1 py-2">
        {question}
        {timer}
        {choices}
        {error ? <p className="px-3 text-center text-xs font-bold text-red-600">{error}</p> : null}
      </div>
    </GameShell>
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
      <GameShell title={t("speed.result")} modeKey="play.speed">
        <div className="grid min-h-0 flex-1 place-items-center px-4">
          <Card>
            <p className="text-center">{error ?? t("common.loading")}</p>
            {error ? (
              <Button className="mt-3 w-full" onClick={onRetry}>
                {t("common.retry")}
              </Button>
            ) : null}
          </Card>
        </div>
      </GameShell>
    );
  }
  const { session, entries } = report;
  const average = session.attempted > 0 ? session.score / session.attempted : null;
  const accuracy = session.attempted > 0 ? Math.round((session.correct / session.attempted) * 100) : null;
  return (
    <GameShell title={t("speed.result")} modeKey="play.speed" scroll>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        <p className="py-1 text-center text-sm font-bold text-stone-600">{t("speed.finished")}</p>
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
                  {average === null ? "—" : faNum(Math.round(average * 100) / 100)}
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
                      {faNum(entry.score)} {t("speed.score")}
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
    </GameShell>
  );
}
