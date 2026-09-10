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
  SpeedPill,
  TimerStrip,
  faNum,
  useGameFit,
} from "./PieceGameLayout";

export type HeavierSideMode = "practice" | "speed";

export const HEAVIER_CHOICES = ["white", "black", "equal"] as const;
export type HeavierChoice = (typeof HEAVIER_CHOICES)[number];

// Dedicated Practice + Speed loop for Heavier Side (کدام طرف سنگین‌تر است؟).
// A real board position is shown read-only; the child mentally totals
// material (P=1 N=3 B=3 R=5 Q=9, K=0) and taps one of three large choices.
// Renders and transports answers only; the material verdict, scoring, and
// the speed clock stay backend-authoritative. Prefetch buffers hold PUBLIC
// puzzle data only (never answers); every submission is graded server-side
// from the stored FEN. The ?mode= URL param (set by the home card's
// Practice/Speed buttons — the buttons ARE the mode selection) picks the
// loop directly; there is no intermediate mode-selection screen.
//
// Layout: full-viewport game shell (no page scroll). Portrait stacks
// question → board → choices; landscape puts the board beside a control
// column. The board is exactly fitted to its area via ResizeObserver.
export function HeavierSidePlay({ mode }: { mode: HeavierSideMode }) {
  return mode === "practice" ? <PracticeLoop /> : <SpeedLoop />;
}

export function choiceLabel(id: string): string {
  if (id === "white") return t("heavierSide.white");
  if (id === "black") return t("heavierSide.black");
  if (id === "equal") return t("heavierSide.equal");
  return id;
}

function correctAnswerLabel(result: AttemptResponse): string {
  const ids = result.detail.correct.concat(result.detail.missed);
  return ids.map(choiceLabel).join("، ") || "—";
}

function ChoiceButtons({
  disabled,
  selected,
  result,
  onChoose,
}: {
  disabled: boolean;
  selected: string | null;
  result: AttemptResponse | null;
  onChoose: (choice: HeavierChoice) => void;
}) {
  return (
    <div className="grid shrink-0 gap-2 px-3 pt-1" role="group" aria-label={t("heavierSide.question")}>
      {HEAVIER_CHOICES.map((choice) => {
        const isSelected = selected === choice;
        const state = result
          ? result.detail.correct.includes(choice)
            ? "correct"
            : result.detail.missed.includes(choice)
              ? "missed"
              : result.detail.wrong.includes(choice)
                ? "wrong"
                : "idle"
          : isSelected
            ? "active"
            : "idle";
        const styles: Record<string, string> = {
          correct: "border-green-500 bg-green-50 text-green-800",
          missed: "border-amber-500 bg-amber-50 text-amber-800",
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
            className={`flex min-h-[56px] items-center justify-center rounded-2xl border-2 px-4 py-3 text-lg font-black transition ${styles[state]}`}
            style={{ touchAction: "manipulation" }}
          >
            {choiceLabel(choice)}
          </button>
        );
      })}
    </div>
  );
}

function AnswerFeedback({ puzzle, result }: { puzzle: Puzzle; result: AttemptResponse }) {
  const isCorrect = result.result === "correct";
  const tone = isCorrect ? "border-green-500 bg-green-50" : "border-red-400 bg-red-50";
  return (
    <div className="shrink-0 px-3" data-testid="feedback">
      <div className={`rounded-2xl border-2 px-3 py-2 ${tone}`}>
        <FeedbackText feedbackKey={result.feedback_key} />
        <p className="mt-1 text-center text-base font-black text-stone-800">
          {t("play.correctAnswer")}: {correctAnswerLabel(result)} · {faNum(result.score)}{" "}
          {t("speed.score")}
        </p>
        {puzzle.explanation ? (
          <p className="mt-0.5 line-clamp-2 text-center text-xs text-stone-600">
            {t("play.explanation")}: {puzzle.explanation}
          </p>
        ) : null}
      </div>
    </div>
  );
}

type PracticePhase = "loading" | "ready" | "submitting" | "feedback" | "error";

// How long practice feedback stays visible before auto-advancing: long
// enough to read green/red plus the correct answer, short enough to keep
// momentum. A manual «next» button is also shown (family convention).
const PRACTICE_FEEDBACK_MS = 1500;

function PracticeLoop() {
  const [phase, setPhase] = useState<PracticePhase>("loading");
  const [current, setCurrent] = useState<Puzzle | null>(null);
  const [buffered, setBuffered] = useState<Puzzle | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
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
      next = await api.nextHeavierPracticePuzzle({ exclude_ids: exclude });
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
      first = await api.nextHeavierPracticePuzzle({ exclude_ids: [] });
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
        .nextHeavierPracticePuzzle({ exclude_ids: current ? [current.id] : [] })
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

  // Immediate selection → validation → feedback → auto-advance. No separate
  // Submit button: tapping a choice submits it.
  async function choose(choice: HeavierChoice) {
    if (phase !== "ready" || !current || busyRef.current) return;
    busyRef.current = true;
    const gen = genRef.current;
    const puzzleId = current.id;
    const hints = usedHints;
    const started = startedAt;
    setSelected(choice);
    setPhase("submitting");
    setError(null);
    try {
      const res = await api.submitAttempt({
        puzzle_id: puzzleId,
        answer: { choice },
        mode: "practice",
        hints_used: hints,
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
    setUsedHints([]);
    setResult(null);
    setError(null);
    setStartedAt(new Date().toISOString());
    setPhase("ready");
  }

  const stat = `${faNum(solved)} · ${faNum(correctTotal)} · ${faNum(scoreTotal)}`;
  if ((phase === "loading" || phase === "error") && !current) {
    return (
      <GameShell title={t("exercises.heavier-side.title")} modeKey="play.practice">
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
      <GameShell title={t("exercises.heavier-side.title")} modeKey="play.practice">
        <div className="grid min-h-0 flex-1 place-items-center px-4">
          <p>{t("common.loading")}</p>
        </div>
      </GameShell>
    );
  }
  const answering = phase === "ready";
  const hints = puzzle.hint_json.hints ?? [];
  const action =
    phase === "feedback" ? (
      <div className="shrink-0 px-3 pb-3 pt-1" data-testid="next-bar">
        <NextBar onNext={advance} onRetry={retryCurrent} />
      </div>
    ) : null;
  const feedback = phase === "feedback" && result ? <AnswerFeedback puzzle={puzzle} result={result} /> : null;
  const question = (
    <QuestionHeader
      prompt={puzzle.prompt_fa || t("heavierSide.question")}
      puzzleKey={puzzle.id}
      hints={hints}
      usedHints={usedHints}
      onUseHint={(id) => setUsedHints((p) => [...p, id])}
    />
  );
  // Read-only board: the position is the question. Choice ids are never
  // squares, so no square state is derived from the result here.
  const board = (
    <BoardZone
      areaRef={areaRef}
      size={size}
      puzzle={puzzle}
      selected={[]}
      result={null}
      disabled={!answering}
      onToggle={() => null}
    />
  );
  const choices = (
    <ChoiceButtons
      disabled={!answering}
      selected={selected}
      result={result}
      onChoose={choose}
    />
  );

  return (
    <GameShell title={t("exercises.heavier-side.title")} modeKey="play.practice" stat={stat}>
      <div ref={rootRef} className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {orientation === "landscape" ? (
          <div className="flex min-h-0 min-w-0 flex-1">
            {board}
            <aside className="flex w-60 shrink-0 flex-col gap-1 overflow-y-auto py-1">
              {question}
              {choices}
              {feedback}
              {action}
            </aside>
          </div>
        ) : (
          <>
            {question}
            {board}
            {choices}
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
      // Best-effort: close an open session when navigating away so its
      // summary/report stays available instead of lingering half-open.
      // Skipped when the backend already confirmed the session is gone.
      const sid = sessionIdRef.current;
      if (sid && sessionAliveRef.current) api.finishHeavierSpeedSession(sid).catch(() => null);
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
      const data = await api.getHeavierSpeedReport(sessionId);
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
      await api.finishHeavierSpeedSession(sessionId).catch(() => null);
      const data = await api.getHeavierSpeedReport(sessionId);
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
      if (prev) await api.finishHeavierSpeedSession(prev).catch(() => null);
      const created = await api.startHeavierSpeedSession();
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
        const batch = await api.prepareHeavierSpeedPuzzles(created.session_id, { count: MIN_BUFFER });
        if (!alive(gen) || sessionIdRef.current !== created.session_id) return;
        for (const p of batch) {
          if (!acc.some((q) => q.id === p.id)) acc.push(p);
        }
      }
      if (acc.length < MIN_BUFFER) throw new Error("buffer_not_ready");
      const started = await api.startHeavierSpeedClock(created.session_id);
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
      const batch = await api.prepareHeavierSpeedPuzzles(sid, { count: REFILL_COUNT });
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

  async function choose(choice: HeavierChoice) {
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
      const res = await api.submitHeavierSpeedAnswer(sid, {
        puzzle_id: puzzle.id,
        answer: { choice },
        hints_used: usedHints,
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
      // Briefly show green/red on the choices, then advance with NO
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
      const puzzle = await api.nextHeavierSpeedPuzzle(sid);
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
      <GameShell title={t("exercises.heavier-side.title")} modeKey="play.speed">
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
      <GameShell title={t("exercises.heavier-side.title")} modeKey="play.speed">
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
  const hints = puzzle.hint_json.hints ?? [];
  const timer = (
    <TimerStrip remainingSec={remainingSec} correct={session.correct} progress={progress} />
  );
  const question = (
    <QuestionHeader
      prompt={puzzle.prompt_fa || t("heavierSide.question")}
      puzzleKey={puzzle.id}
      hints={hints}
      usedHints={usedHints}
      onUseHint={(id) => setUsedHints((p) => [...p, id])}
    />
  );
  const board = (
    <BoardZone
      areaRef={areaRef}
      size={size}
      puzzle={puzzle}
      selected={[]}
      result={null}
      disabled={result !== null || busy}
      onToggle={() => null}
      overlay={result ? <SpeedPill result={result} /> : null}
    />
  );
  const choices = (
    <ChoiceButtons
      disabled={result !== null || busy}
      selected={selected}
      result={result}
      onChoose={choose}
    />
  );

  return (
    <GameShell title={t("exercises.heavier-side.title")} modeKey="play.speed">
      <div ref={rootRef} className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {orientation === "landscape" ? (
          <div className="flex min-h-0 min-w-0 flex-1">
            {board}
            <aside className="flex w-60 shrink-0 flex-col gap-1 overflow-y-auto py-1">
              {question}
              {timer}
              {choices}
              {error ? <p className="px-3 text-center text-xs font-bold text-red-600">{error}</p> : null}
            </aside>
          </div>
        ) : (
          <>
            {question}
            {timer}
            {board}
            {choices}
            {error ? <p className="px-3 text-center text-xs font-bold text-red-600">{error}</p> : null}
          </>
        )}
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
