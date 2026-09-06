import { useEffect, useRef, useState } from "react";
import { api, apiDetail, apiStatus } from "../../api/client";
import type { AttemptResponse, Puzzle, SpeedReport, SpeedSummary } from "../../api/types";
import { t } from "../../i18n";
import { savePracticeAttempt } from "../../lib/localProgress";
import { playSuccess } from "../../lib/sound";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { PageHeader } from "../ui/PageHeader";
import {
  BalanceScale,
  MAX_PAN_PIECES,
  PieceInventory,
  asKindList,
  totalOf,
  type PanItem,
} from "./BalanceScaleView";
import { QuestionHeader, SpeedPill, TimerStrip, faNum } from "./PieceGameLayout";

export type BalanceScaleMode = "practice" | "speed";

// How long speed success feedback shows before auto-advancing: very
// brief, then the next puzzle. No manual Next button in speed.
export const SPEED_FEEDBACK_MS = 500;
export const FULL_FLASH_MS = 1500;

// Dedicated Practice + Speed loop for Balance Scale (Exercise 10). Renders
// and transports answers only; target totals, optimal counts, scoring,
// and the speed clock stay backend-authoritative. The ?mode= URL param
// picks the loop directly; there is no intermediate mode-selection screen.
//
// No chessboard: the black left pan is the immutable target, the child
// adds unlimited white pieces to the right pan (10 slots). Reaching exact
// balance auto-submits the white pieces as one attempt; the server
// recomputes the target and the score from scratch.
export function BalanceScalePlay({ mode }: { mode: BalanceScaleMode }) {
  return mode === "practice" ? <PracticeLoop /> : <SpeedLoop />;
}

/** Public task data carried by a puzzle row (optimal counts never leave the server). */
export function leftOf(puzzle: Puzzle): string[] {
  const pos = puzzle.position_json as Record<string, unknown>;
  return asKindList(pos.left);
}

/** Authoritative submission payload: the placed white pieces.
 * Never ships scores, optimal counts, or correctness flags. */
export function answerForPieces(pieces: string[]): { pieces: string[] } {
  return { pieces: [...pieces] };
}

type PracticePhase = "loading" | "ready" | "submitting" | "feedback" | "error";

function PracticeLoop() {
  const [phase, setPhase] = useState<PracticePhase>("loading");
  const [current, setCurrent] = useState<Puzzle | null>(null);
  const [buffered, setBuffered] = useState<Puzzle | null>(null);
  const [right, setRight] = useState<PanItem[]>([]);
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>("");
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fullFlash, setFullFlash] = useState(false);
  const [solved, setSolved] = useState(0);
  const [scoreTotal, setScoreTotal] = useState(0);
  const uidRef = useRef(0);
  const genRef = useRef(0);
  const mountedRef = useRef(true);
  const busyRef = useRef(false);
  const currentIdRef = useRef<number | null>(null);
  const fullTimerRef = useRef<number | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      genRef.current += 1;
      if (fullTimerRef.current !== null) window.clearTimeout(fullTimerRef.current);
    };
  }, []);

  function alive(gen: number) {
    return mountedRef.current && genRef.current === gen;
  }

  function resetFor(puzzle: Puzzle) {
    currentIdRef.current = puzzle.id;
    setCurrent(puzzle);
    setRight([]);
    setUsedHints([]);
    setResult(null);
    setError(null);
    setFullFlash(false);
    setStartedAt(new Date().toISOString());
    setPhase("ready");
  }

  async function refill(exclude: number[]) {
    const gen = genRef.current;
    let next: Puzzle | null = null;
    try {
      next = await api.nextBalancePracticePuzzle({ exclude_ids: exclude });
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
      first = await api.nextBalancePracticePuzzle({ exclude_ids: [] });
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
        .nextBalancePracticePuzzle({ exclude_ids: current ? [current.id] : [] })
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

  function retryCurrent() {
    if (!current || busyRef.current) return;
    const gen = ++genRef.current;
    void gen;
    resetFor(current);
  }

  function flagFull() {
    setFullFlash(true);
    if (fullTimerRef.current !== null) window.clearTimeout(fullTimerRef.current);
    fullTimerRef.current = window.setTimeout(() => {
      fullTimerRef.current = null;
      setFullFlash(false);
    }, FULL_FLASH_MS);
  }

  function addPiece(kind: string) {
    if (phase !== "ready" || result) return;
    if (right.length >= MAX_PAN_PIECES) {
      // Capacity feedback only: never a wrong answer, never scored.
      flagFull();
      return;
    }
    uidRef.current += 1;
    setRight((prev) => [...prev, { uid: uidRef.current, kind }]);
  }

  function removeUid(uid: number) {
    if (phase !== "ready" || result) return;
    setRight((prev) => prev.filter((p) => p.uid !== uid));
  }

  async function submit(kinds: string[]) {
    if (!current || busyRef.current) return;
    busyRef.current = true;
    const gen = genRef.current;
    const puzzleId = current.id;
    const hints = usedHints;
    const started = startedAt;
    setPhase("submitting");
    setError(null);
    try {
      const res = await api.submitAttempt({
        puzzle_id: puzzleId,
        answer: answerForPieces(kinds),
        mode: "practice",
        hints_used: hints,
        started_at: started,
      });
      if (!alive(gen)) return;
      playSuccess();
      setResult(res);
      setSolved((n) => n + 1);
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

  // Auto-submit the moment the pans balance exactly. No Submit button:
  // experimentation is free, only the balanced state is graded.
  const puzzle = current;
  const left = puzzle ? leftOf(puzzle) : [];
  const leftTotal = totalOf(left);
  const rightKinds = right.map((p) => p.kind);
  const balanced = right.length > 0 && totalOf(rightKinds) === leftTotal;
  useEffect(() => {
    if (phase === "ready" && balanced && !busyRef.current) {
      void submit(rightKinds);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [balanced, phase]);

  if ((phase === "loading" || phase === "error") && !current) {
    return (
      <div>
        <PageHeader title={t("exercises.balance-scale.title")} subtitle={t("balance.intro")} />
        <Card>
          <p className="text-center">{phase === "error" ? (error ?? t("common.error")) : t("common.loading")}</p>
          {phase === "error" ? (
            <Button className="mt-3 w-full" onClick={loadInitial}>
              {t("common.retry")}
            </Button>
          ) : null}
        </Card>
      </div>
    );
  }
  if (!puzzle) {
    return (
      <div>
        <PageHeader title={t("exercises.balance-scale.title")} subtitle={t("balance.intro")} />
        <p className="text-center">{t("common.loading")}</p>
      </div>
    );
  }

  const leftItems: PanItem[] = left.map((kind, i) => ({ uid: -(i + 1), kind }));
  const hints = puzzle.hint_json.hints ?? [];
  const locked = result !== null || phase === "submitting";
  const full = right.length >= MAX_PAN_PIECES;

  return (
    <div className="mx-auto w-full max-w-2xl overflow-x-clip pb-6">
      <PageHeader title={t("exercises.balance-scale.title")} subtitle={t("balance.intro")} />
      <div className="mb-3 flex items-center gap-2">
        <Badge>
          {t("practice.solved")}: {faNum(solved)}
        </Badge>
        <Badge>
          {t("speed.score")}: {faNum(scoreTotal)}
        </Badge>
      </div>

      <QuestionHeader
        prompt={t("balance.howto")}
        puzzleKey={puzzle.id}
        hints={hints}
        usedHints={usedHints}
        onUseHint={(id) => setUsedHints((p) => [...p, id])}
      />

      <Card className="mt-2">
        <BalanceScale
          leftItems={leftItems}
          rightItems={right}
          balanced={balanced || result?.result === "correct"}
          locked={locked}
          onRemoveRight={removeUid}
        />
        {balanced || result?.result === "correct" ? (
          <p className="mt-2 text-center text-lg font-black text-green-700" data-testid="balanced-message" role="status">
            {t("balance.balanced")}
          </p>
        ) : null}
      </Card>

      {phase === "feedback" && result ? (
        <Card className="mt-3" data-testid="practice-feedback">
          <p className="text-center text-sm font-bold text-stone-600">
            {t("balance.score")}: <span className="text-2xl font-black text-violet-700">{faNum(result.score)}</span>
          </p>
          {puzzle.explanation ? (
            <p className="mt-2 text-center text-sm text-stone-600">
              {t("play.explanation")}: {puzzle.explanation}
            </p>
          ) : null}
          <Button className="mt-3 w-full" onClick={advance} data-testid="next-question">
            {t("play.next")}
          </Button>
        </Card>
      ) : (
        <div>
          <Card className="mt-3">
            <p className="mb-2 text-center text-sm font-black text-stone-700">{t("balance.inventory")}</p>
            <PieceInventory onAdd={addPiece} disabled={locked} full={full} />
            {fullFlash ? (
              <p className="mt-2 text-center text-sm font-bold text-amber-700" role="status">
                {t("balance.panFull")}
              </p>
            ) : null}
          </Card>
          <div className="mt-3 flex gap-2">
            <Button variant="secondary" className="flex-1" onClick={retryCurrent} disabled={locked}>
              {t("play.clear")}
            </Button>
          </div>
          {error ? <p className="mt-2 text-center text-sm font-bold text-red-600">{error}</p> : null}
        </div>
      )}
    </div>
  );
}

type SpeedPhase = "preparing" | "active" | "report";

const MIN_BUFFER = 20;
const REFILL_AT = 12;
const REFILL_COUNT = 12;
const MAX_SKIPS = 3;

function SpeedLoop() {
  const [phase, setPhase] = useState<SpeedPhase>("preparing");
  const [session, setSession] = useState<SpeedSummary | null>(null);
  const [, setQueueTick] = useState(0);
  const [current, setCurrent] = useState<Puzzle | null>(null);
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [report, setReport] = useState<SpeedReport | null>(null);
  const [right, setRight] = useState<PanItem[]>([]);
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fullFlash, setFullFlash] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const uidRef = useRef(0);
  const deadlineRef = useRef(0);
  const finishingRef = useRef(false);
  const refillingRef = useRef(false);
  const busyRef = useRef(false);
  const submitRef = useRef(false);
  const transitionRef = useRef<number | null>(null);
  const consecutiveSkipRef = useRef(0);
  const sessionAliveRef = useRef(true);
  const genRef = useRef(0);
  const mountedRef = useRef(true);
  const sessionIdRef = useRef<string | null>(null);
  const queueRef = useRef<Puzzle[]>([]);
  const currentRef = useRef<Puzzle | null>(null);
  const fullTimerRef = useRef<number | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      genRef.current += 1;
      if (transitionRef.current !== null) {
        clearTimeout(transitionRef.current);
        transitionRef.current = null;
      }
      if (fullTimerRef.current !== null) window.clearTimeout(fullTimerRef.current);
      const sid = sessionIdRef.current;
      if (sid && sessionAliveRef.current) api.finishBalanceSpeedSession(sid).catch(() => null);
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

  async function dieToReport(sessionId: string, gen: number) {
    sessionAliveRef.current = false;
    busyRef.current = false;
    submitRef.current = false;
    if (alive(gen)) setBusy(false);
    try {
      const data = await api.getBalanceSpeedReport(sessionId);
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
    setRight([]);
    setUsedHints([]);
    setResult(null);
    setError(null);
    setFullFlash(false);
    submitRef.current = false;
    setStartedAt(new Date().toISOString());
  }

  async function finishToReport(sessionId: string, gen: number) {
    if (finishingRef.current) return;
    finishingRef.current = true;
    cancelTransition();
    try {
      await api.finishBalanceSpeedSession(sessionId).catch(() => null);
      const data = await api.getBalanceSpeedReport(sessionId);
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

  async function boot() {
    const gen = ++genRef.current;
    busyRef.current = false;
    submitRef.current = false;
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
      if (prev) await api.finishBalanceSpeedSession(prev).catch(() => null);
      const created = await api.startBalanceSpeedSession();
      if (!alive(gen)) return;
      sessionIdRef.current = created.session_id;
      setSession({ ...created, attempted: 0, correct: 0, partial: 0, wrong: 0, score: 0 });
      const acc: Puzzle[] = [];
      let guard = 0;
      while (acc.length < MIN_BUFFER && guard < 6) {
        guard += 1;
        const batch = await api.prepareBalanceSpeedPuzzles(created.session_id, { count: MIN_BUFFER });
        if (!alive(gen) || sessionIdRef.current !== created.session_id) return;
        for (const p of batch) {
          if (!acc.some((q) => q.id === p.id)) acc.push(p);
        }
      }
      if (acc.length < MIN_BUFFER) throw new Error("buffer_not_ready");
      const started = await api.startBalanceSpeedClock(created.session_id);
      if (!alive(gen) || sessionIdRef.current !== created.session_id) return;
      setSession({ ...started, attempted: 0, correct: 0, partial: 0, wrong: 0, score: 0 });
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

  async function refillIfNeeded() {
    const sid = sessionIdRef.current;
    const gen = genRef.current;
    if (!sid || refillingRef.current) return;
    if (queueRef.current.length >= REFILL_AT) return;
    refillingRef.current = true;
    try {
      const batch = await api.prepareBalanceSpeedPuzzles(sid, { count: REFILL_COUNT });
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

  function flagFull() {
    setFullFlash(true);
    if (fullTimerRef.current !== null) window.clearTimeout(fullTimerRef.current);
    fullTimerRef.current = window.setTimeout(() => {
      fullTimerRef.current = null;
      setFullFlash(false);
    }, FULL_FLASH_MS);
  }

  function addPiece(kind: string) {
    if (phase !== "active" || result || busyRef.current || submitRef.current) return;
    if (right.length >= MAX_PAN_PIECES) {
      flagFull();
      return;
    }
    uidRef.current += 1;
    setRight((prev) => [...prev, { uid: uidRef.current, kind }]);
  }

  function removeUid(uid: number) {
    if (phase !== "active" || result || busyRef.current || submitRef.current) return;
    setRight((prev) => prev.filter((p) => p.uid !== uid));
  }

  async function submitFinal(kinds: string[]) {
    const puzzle = currentRef.current;
    const sid = sessionIdRef.current;
    if (phase !== "active" || !puzzle || !sid || busyRef.current || submitRef.current) return;
    busyRef.current = true;
    submitRef.current = true;
    const gen = genRef.current;
    setBusy(true);
    setError(null);
    try {
      const res = await api.submitBalanceSpeedAnswer(sid, {
        puzzle_id: puzzle.id,
        answer: answerForPieces(kinds),
        hints_used: usedHints,
        started_at: startedAt,
      });
      if (!alive(gen) || sessionIdRef.current !== sid) {
        busyRef.current = false;
        return;
      }
      playSuccess();
      setResult(res.attempt);
      setSession(res.session);
      consecutiveSkipRef.current = 0;
      anchorDeadline(res.session.remaining_ms);
      // Very brief success feedback, then auto-advance with NO manual
      // button. The timer keeps running; expiry cancels this.
      transitionRef.current = window.setTimeout(() => {
        transitionRef.current = null;
        if (!alive(gen) || sessionIdRef.current !== sid) {
          busyRef.current = false;
          return;
        }
        advance();
      }, SPEED_FEEDBACK_MS);
    } catch (e) {
      if (!alive(gen)) {
        busyRef.current = false;
        return;
      }
      if (isGone(e)) {
        busyRef.current = false;
        submitRef.current = false;
        if (alive(gen)) setBusy(false);
        await finishToReport(sid, gen);
        setError(t("speed.expired"));
      } else if (isSessionLost(e)) {
        await dieToReport(sid, gen);
      } else if (isUnknownPuzzle(e)) {
        consecutiveSkipRef.current += 1;
        if (consecutiveSkipRef.current >= MAX_SKIPS) {
          await dieToReport(sid, gen);
        } else {
          busyRef.current = false;
          submitRef.current = false;
          if (alive(gen)) setBusy(false);
          advance();
        }
      } else {
        busyRef.current = false;
        submitRef.current = false;
        setError(t("common.error"));
        if (alive(gen)) setBusy(false);
      }
    }
  }

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
    busyRef.current = true;
    setBusy(true);
    setError(null);
    try {
      const puzzle = await api.nextBalanceSpeedPuzzle(sid);
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
      submitRef.current = false;
      if (alive(genRef.current)) setBusy(false);
    }
  }

  // Speed also auto-submits on exact balance (no Submit button).
  const speedPuzzle = current;
  const speedLeft = speedPuzzle ? leftOf(speedPuzzle) : [];
  const speedLeftTotal = totalOf(speedLeft);
  const speedRightKinds = right.map((p) => p.kind);
  const speedBalanced = speedRightKinds.length > 0 && totalOf(speedRightKinds) === speedLeftTotal;
  useEffect(() => {
    if (phase === "active" && speedBalanced && currentRef.current) {
      void submitFinal(speedRightKinds);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [speedBalanced, phase]);

  if (phase === "preparing") {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <PageHeader title={t("exercises.balance-scale.title")} subtitle={t("speed.howto")} />
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
    );
  }

  if (phase === "report") {
    return <SpeedReportView report={report} error={error} onRetry={boot} />;
  }

  const puzzle = current;
  if (!session || !puzzle) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <PageHeader title={t("exercises.balance-scale.title")} subtitle={t("speed.howto")} />
        <Card>
          <p className="text-center">{error ?? t("common.loading")}</p>
          {error ? (
            <Button className="mt-3 w-full" onClick={boot}>
              {t("common.retry")}
            </Button>
          ) : null}
        </Card>
      </div>
    );
  }

  const leftItems: PanItem[] = speedLeft.map((kind, i) => ({ uid: -(i + 1), kind }));
  const hints = puzzle.hint_json.hints ?? [];
  const totalMs = session.duration_s * 1000;
  const progress = Math.max(0, Math.min(1, remainingMs / totalMs));
  const full = right.length >= MAX_PAN_PIECES;

  return (
    <div className="relative mx-auto w-full max-w-2xl overflow-x-clip pb-6">
      <PageHeader title={t("exercises.balance-scale.title")} subtitle={t("speed.howto")} />
      <TimerStrip remainingSec={remainingSec} correct={session.correct} progress={progress} />
      <QuestionHeader
        prompt={t("balance.howto")}
        puzzleKey={puzzle.id}
        hints={hints}
        usedHints={usedHints}
        onUseHint={(id) => setUsedHints((p) => [...p, id])}
      />
      <Card className="relative mt-2">
        {result ? <SpeedPill result={result} /> : null}
        <BalanceScale
          leftItems={leftItems}
          rightItems={right}
          balanced={speedBalanced || result?.result === "correct"}
          locked={result !== null || busy}
          onRemoveRight={removeUid}
        />
        {speedBalanced || result?.result === "correct" ? (
          <p className="mt-2 text-center text-lg font-black text-green-700" data-testid="balanced-message" role="status">
            {t("balance.balanced")}
          </p>
        ) : null}
      </Card>
      <Card className="mt-3">
        <p className="mb-2 text-center text-sm font-black text-stone-700">{t("balance.inventory")}</p>
        <PieceInventory onAdd={addPiece} disabled={result !== null || busy} full={full} />
        {fullFlash ? (
          <p className="mt-2 text-center text-sm font-bold text-amber-700" role="status">
            {t("balance.panFull")}
          </p>
        ) : null}
      </Card>
      {error ? <p className="mt-2 text-center text-sm font-bold text-red-600">{error}</p> : null}
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
      <div className="mx-auto w-full max-w-2xl">
        <PageHeader title={t("speed.result")} subtitle={t("speed.howto")} />
        <Card>
          <p className="text-center">{error ?? t("common.loading")}</p>
          {error ? (
            <Button className="mt-3 w-full" onClick={onRetry}>
              {t("common.retry")}
            </Button>
          ) : null}
        </Card>
      </div>
    );
  }
  const { session, entries } = report;
  const average = session.attempted > 0 ? session.score / session.attempted : null;
  const accuracy = session.attempted > 0 ? Math.round((session.correct / session.attempted) * 100) : null;
  return (
    <div className="mx-auto w-full max-w-2xl pb-6">
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
  );
}
